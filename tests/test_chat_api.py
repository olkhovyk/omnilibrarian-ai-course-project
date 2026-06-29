from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.rate_limit import RateLimitExceeded


class FakeChatService:
    def __init__(self) -> None:
        self.warmup_calls = 0

    def warmup(self) -> None:
        self.warmup_calls += 1

    def answer(self, *, message: str, session_id: str, game_id: str | None) -> dict:
        return {
            "answer": f"answer for {message}",
            "game_id": game_id or "bg3",
            "intent": "rag",
            "sources": [{"id": 1, "title": "Fireball"}],
            "tool_calls": [],
            "trace": [{"step": "fake", "session_id": session_id}],
            "latency_ms": 12,
        }

    def stream_answer(self, *, message: str, session_id: str, game_id: str | None):
        yield 'event: token\ndata: {"content":"hello"}\n\n'
        yield (
            'event: final\n'
            'data: {"answer":"hello","game_id":"bg3","intent":"rag","sources":[],"tool_calls":[],"trace":[],"latency_ms":12}\n\n'
        )


class RejectingRateLimiter:
    def check(self, identifier: str) -> None:
        raise RateLimitExceeded(limit_name="minute", retry_after_seconds=60)


def test_chat_endpoint_returns_rag_response_from_service():
    app = create_app(chat_service=FakeChatService())
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "message": "Яка шкода від Fireball?",
            "session_id": "test-session",
            "game_id": "bg3",
            "stream": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "answer for Яка шкода від Fireball?",
        "game_id": "bg3",
        "intent": "rag",
        "sources": [{"id": 1, "title": "Fireball"}],
        "tool_calls": [],
        "trace": [{"step": "fake", "session_id": "test-session"}],
        "latency_ms": 12,
    }


def test_app_startup_warms_chat_service_when_enabled():
    chat_service = FakeChatService()
    app = create_app(chat_service=chat_service, warmup_on_startup=True)

    with TestClient(app):
        pass

    assert chat_service.warmup_calls == 1


def test_chat_endpoint_returns_429_when_rate_limited():
    app = create_app(
        chat_service=FakeChatService(),
        rate_limiter=RejectingRateLimiter(),
        rate_limit_enabled=True,
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "message": "Fireball damage",
            "session_id": "test-session",
            "game_id": "bg3",
            "stream": False,
        },
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {
        "error": "rate_limit_exceeded",
        "limit": "minute",
        "retry_after_seconds": 60,
    }


def test_chat_endpoint_streams_sse_when_stream_is_true():
    app = create_app(chat_service=FakeChatService())
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={
            "message": "Fireball damage",
            "session_id": "test-session",
            "game_id": "bg3",
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token\ndata: {"content":"hello"}' in response.text
    assert 'event: final\ndata: {"answer":"hello"' in response.text
