from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass(frozen=True)
class SessionTurn:
    role: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


class InMemorySessionStore:
    def __init__(self, *, max_turns_per_session: int = 12, now=None) -> None:
        self.max_turns_per_session = max_turns_per_session
        self._sessions: dict[str, deque[SessionTurn]] = defaultdict(lambda: deque(maxlen=max_turns_per_session))
        self._lock = Lock()
        self._now = now or (lambda: datetime.now(UTC))

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        if not session_id:
            return []
        with self._lock:
            return [turn.to_dict() for turn in self._sessions.get(session_id, [])]

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        if not session_id or not content:
            return
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported session role: {role}")
        turn = SessionTurn(role=role, content=content, created_at=self._now().isoformat())
        with self._lock:
            self._sessions[session_id].append(turn)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


SessionStore = InMemorySessionStore
