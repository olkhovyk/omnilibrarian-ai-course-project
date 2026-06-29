import importlib.util
from pathlib import Path

import httpx


def _load_streamlit_app_module():
    module_path = Path("apps") / "streamlit_app" / "app.py"
    spec = importlib.util.spec_from_file_location("streamlit_app", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, api_url: str, json: dict):
        self.calls += 1
        if self.calls == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json={"answer": "ok"}, request=httpx.Request("POST", api_url))


class FakeStreamResponse:
    def __init__(self) -> None:
        self.lines = [
            'event: token',
            'data: {"content":"Hello "}',
            '',
            'event: token',
            'data: {"content":"world"}',
            '',
            'event: final',
            'data: {"sources":[{"title":"Fireball"}],"trace":[{"step":"generate_answer"}]}',
            '',
        ]

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        return iter(self.lines)


class FakeStreamingClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method: str, api_url: str, json: dict):
        return _Context(FakeStreamResponse())


class _Context:
    def __init__(self, value) -> None:
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_call_chat_api_retries_when_api_is_not_ready(monkeypatch):
    streamlit_app = _load_streamlit_app_module()
    client = FakeClient(timeout=120)
    monkeypatch.setattr(streamlit_app.httpx, "Client", lambda timeout: client)
    monkeypatch.setattr(streamlit_app.time, "sleep", lambda _seconds: None)

    response = streamlit_app._call_chat_api(
        api_url="http://127.0.0.1:8000/v1/chat",
        message="Who is Astarion?",
        session_id="s1",
        game_id="bg3",
    )

    assert response == {"answer": "ok"}
    assert client.calls == 2


def test_stream_chat_api_parses_sse_token_and_final_events(monkeypatch):
    streamlit_app = _load_streamlit_app_module()
    monkeypatch.setattr(streamlit_app.httpx, "Client", lambda timeout: FakeStreamingClient(timeout))

    events = list(
        streamlit_app._stream_chat_api(
            api_url="http://127.0.0.1:8000/v1/chat",
            message="Fireball damage",
            session_id="s1",
            game_id="bg3",
        )
    )

    assert events == [
        {"type": "token", "content": "Hello "},
        {"type": "token", "content": "world"},
        {"type": "final", "sources": [{"title": "Fireball"}], "trace": [{"step": "generate_answer"}]},
    ]


def test_load_tenants_reads_configured_games():
    streamlit_app = _load_streamlit_app_module()

    tenants = streamlit_app._load_tenants("configs/tenants.yaml")

    assert tenants == [
        {"game_id": "bg3", "display_name": "Baldur's Gate 3"},
        {"game_id": "blue_prince", "display_name": "Blue Prince"},
    ]


def test_load_tenants_falls_back_to_bg3_when_config_missing():
    streamlit_app = _load_streamlit_app_module()

    tenants = streamlit_app._load_tenants("missing-tenants.json")

    assert tenants == [{"game_id": "bg3", "display_name": "Baldur's Gate 3"}]


def test_chat_placeholder_reflects_auto_or_selected_game():
    streamlit_app = _load_streamlit_app_module()

    assert streamlit_app._chat_placeholder(game_id="auto", game_labels={"auto": "Auto detect"}) == (
        "Ask about any configured game"
    )
    assert streamlit_app._chat_placeholder(game_id="blue_prince", game_labels={"blue_prince": "Blue Prince"}) == (
        "Ask about Blue Prince"
    )
