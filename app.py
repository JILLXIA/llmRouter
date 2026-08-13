"""Streamlit UI for the bare-minimum LLM router."""

from __future__ import annotations

import logging

import streamlit as st

from llm_router.config import Settings, load_settings
from llm_router.router import LLMRouter, RouterError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@st.cache_resource(show_spinner=False)
def get_router() -> LLMRouter:
    return LLMRouter(load_settings())


def routing_caption(routing: dict[str, str]) -> str:
    return (
        f"Intent: {routing['intent']} · "
        f"Classified by: {routing['classifier_source']} · "
        f"Model: {routing['model']}"
    )


def render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if routing := message.get("routing"):
                st.caption(routing_caption(routing))


def render_sidebar(settings: Settings) -> None:
    with st.sidebar:
        st.header("Model routes")
        st.text(f"Intent: {settings.intent_model}")
        st.text(f"Code: {settings.high_quality_model}")
        st.text(f"Analysis: {settings.balanced_model}")
        st.text(f"General: {settings.economy_model}")

        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
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

    if "messages" not in st.session_state:
        st.session_state.messages = []

    render_sidebar(settings)
    render_history()

    prompt = st.chat_input("Ask me anything...")
    if not prompt:
        return

    # Pass the old messages to the model, then store and display the new user message.
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        with st.spinner("Choosing the best model..."):
            result = get_router().chat(prompt, history)
    except RouterError as error:
        st.error(str(error))
        return

    routing = result.routing_metadata()
    st.session_state.messages.append(
        {"role": "assistant", "content": result.response, "routing": routing}
    )
    with st.chat_message("assistant"):
        st.markdown(result.response)
        st.caption(routing_caption(routing))


if __name__ == "__main__":
    main()
