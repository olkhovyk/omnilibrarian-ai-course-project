import json
import os
from pathlib import Path
import time

import httpx
import streamlit as st
from dotenv import load_dotenv

from omnilibrarian.tenants.registry import load_tenant_registry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TENANTS_PATH = PROJECT_ROOT / "configs" / "tenants.yaml"
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    st.set_page_config(page_title="OmniLibrarian", layout="wide")
    st.title("OmniLibrarian")

    api_url = os.getenv("OMNILIBRARIAN_API_URL", "http://localhost:8000/v1/chat")
    tenants = _load_tenants()
    game_ids = ["auto", *[tenant["game_id"] for tenant in tenants]]
    game_labels = {"auto": "Auto detect", **{tenant["game_id"]: tenant["display_name"] for tenant in tenants}}
    with st.sidebar:
        st.subheader("Settings")
        game_id = st.selectbox(
            "Game",
            game_ids,
            index=0,
            format_func=lambda value: game_labels.get(value, value),
        )
        session_id = st.text_input("Session ID", value="streamlit-demo")
        show_debug = st.toggle("Debug", value=True)
        st.caption(api_url)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(_chat_placeholder(game_id=game_id, game_labels=game_labels))
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        answer_parts: list[str] = []
        response: dict = {}
        answer_placeholder = st.empty()
        with st.spinner("Retrieving context..."):
            try:
                for event in _stream_chat_api(
                    api_url=api_url,
                    message=prompt,
                    session_id=session_id,
                    game_id=game_id,
                ):
                    if event["type"] == "token":
                        answer_parts.append(event.get("content", ""))
                        answer_placeholder.markdown("".join(answer_parts))
                    elif event["type"] == "final":
                        response = event
            except Exception as exc:
                st.error(str(exc))
                return

        answer = response.get("answer") or "".join(answer_parts)
        answer_placeholder.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

        sources = response.get("sources") or []
        if sources:
            st.subheader("Sources")
            for source in sources:
                source_id = source.get("id")
                title = source.get("title")
                section = source.get("section")
                url = source.get("url")
                st.markdown(f"[{source_id}] [{title} - {section}]({url})")

        if show_debug:
            with st.expander("Trace", expanded=False):
                st.json(response.get("trace") or [])


def _call_chat_api(*, api_url: str, message: str, session_id: str, game_id: str, retries: int = 5) -> dict:
    payload = {
        "message": message,
        "session_id": session_id,
        "game_id": game_id,
        "stream": False,
    }
    with httpx.Client(timeout=120) as client:
        for attempt in range(1, retries + 1):
            try:
                response = client.post(api_url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                if attempt == retries:
                    raise
                time.sleep(1)
    raise RuntimeError("Chat API did not return a response.")


def _load_tenants(path: str | Path = TENANTS_PATH) -> list[dict[str, str]]:
    try:
        registry = load_tenant_registry(path)
        return [
            {
                "game_id": game_id,
                "display_name": registry.get(game_id).display_name,
            }
            for game_id in registry.game_ids()
        ]
    except Exception:
        return [{"game_id": "bg3", "display_name": "Baldur's Gate 3"}]


def _chat_placeholder(*, game_id: str, game_labels: dict[str, str]) -> str:
    if game_id == "auto":
        return "Ask about any configured game"
    return f"Ask about {game_labels.get(game_id, game_id)}"


def _stream_chat_api(*, api_url: str, message: str, session_id: str, game_id: str):
    payload = {
        "message": message,
        "session_id": session_id,
        "game_id": game_id,
        "stream": True,
    }
    with httpx.Client(timeout=120) as client:
        with client.stream("POST", api_url, json=payload) as response:
            response.raise_for_status()
            yield from _parse_sse_lines(response.iter_lines())


def _parse_sse_lines(lines):
    event_type: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if not line:
            if event_type and data_lines:
                payload = json.loads("\n".join(data_lines))
                payload["type"] = event_type
                yield payload
            event_type = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())


if __name__ == "__main__":
    main()
