from datetime import UTC, datetime, timedelta

import pytest

from omnilibrarian.memory import InMemorySessionStore


def test_in_memory_session_store_appends_and_returns_history_copy():
    current = datetime(2026, 6, 7, 10, 0, tzinfo=UTC)
    store = InMemorySessionStore(now=lambda: current)

    store.append_turn("s1", "user", "Who is Astarion?")
    store.append_turn("s1", "assistant", "Astarion is a vampire spawn.")

    history = store.get_history("s1")

    assert history == [
        {"role": "user", "content": "Who is Astarion?", "created_at": current.isoformat()},
        {"role": "assistant", "content": "Astarion is a vampire spawn.", "created_at": current.isoformat()},
    ]
    history.append({"role": "user", "content": "mutated", "created_at": current.isoformat()})
    assert len(store.get_history("s1")) == 2


def test_in_memory_session_store_caps_history_per_session():
    current = datetime(2026, 6, 7, 10, 0, tzinfo=UTC)

    def now():
        return current + timedelta(seconds=len(store.get_history("s1")))

    store = InMemorySessionStore(max_turns_per_session=3, now=now)

    store.append_turn("s1", "user", "one")
    store.append_turn("s1", "assistant", "two")
    store.append_turn("s1", "user", "three")
    store.append_turn("s1", "assistant", "four")

    assert [turn["content"] for turn in store.get_history("s1")] == ["two", "three", "four"]


def test_in_memory_session_store_rejects_unknown_roles():
    store = InMemorySessionStore()

    with pytest.raises(ValueError, match="Unsupported session role"):
        store.append_turn("s1", "system", "hidden")
