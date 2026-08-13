from __future__ import annotations

import logging

import streamlit as st

from llm_router.config import Settings, load_settings
from llm_router.router import LLMRouter, RouterError
from llm_router.storage import (
    clear_messages,
    get_or_create_session,
    load_messages,
    save_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@st.cache_resource(show_spinner=False)
def get_router() -> LLMRouter:
    return LLMRouter(load_settings())


def routing_caption(routing: dict[str, str | int | float]) -> str:
    return (
        f"Intent: {routing['intent']} · "
        f"Classified by: {routing['classifier_source']} · "
        f"Model: {routing['model']} · "
        f"Tokens: {routing.get('input_tokens', 0)} in + "
        f"{routing.get('output_tokens', 0)} out = "
        f"{routing.get('total_tokens', 0)} total"
    )


def render_history(messages: list[dict[str, object]]) -> None:
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if routing := message.get("routing"):
                st.caption(routing_caption(routing))


def render_sidebar(settings: Settings, session_id: str) -> None:
    with st.sidebar:
        st.header("Anonymous session")
        st.text(session_id)

        st.header("Model routes")
        st.text(f"Intent: {settings.intent_model}")
        st.text(f"Code: {settings.high_quality_model}")
        st.text(f"Analysis: {settings.balanced_model}")
        st.text(f"General: {settings.economy_model}")

        if st.button("Clear chat", use_container_width=True):
            clear_messages(settings.database_path, session_id)
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="LLM Router Chat", page_icon="🔀")
    st.title("LLM Router Chat")
    st.write("Ask a question and the router will choose an OpenAI model for it.")

    try:
        settings = load_settings()
    except ValueError as error:
        st.error(str(error))
        st.stop()

    requested_session_id = st.query_params.get("session_id")
    session_id = get_or_create_session(
        settings.database_path,
        requested_session_id,
    )
    if requested_session_id != session_id:
        st.query_params["session_id"] = session_id

    messages = load_messages(settings.database_path, session_id)
    render_sidebar(settings, session_id)
    render_history(messages)

    prompt = st.chat_input("Ask me anything...")
    if not prompt:
        return

    save_message(settings.database_path, session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed_text = ""

        def render_chunk(chunk: str) -> None:
            nonlocal streamed_text
            streamed_text += chunk
            placeholder.markdown(f"{streamed_text}▌")

        try:
            with st.spinner("Choosing the best model..."):
                result = get_router().chat(prompt, messages, on_chunk=render_chunk)
        except RouterError as error:
            placeholder.empty()
            st.error(str(error))
            return

        placeholder.markdown(result.response)
        routing = result.routing_metadata()
        st.caption(routing_caption(routing))

    save_message(
        settings.database_path,
        session_id,
        "assistant",
        result.response,
        routing,
    )


if __name__ == "__main__":
    main()
