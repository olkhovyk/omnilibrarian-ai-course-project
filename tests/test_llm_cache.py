from omnilibrarian.cache.llm_cache import (
    LLMCachePayload,
    RedisLLMCache,
    build_llm_cache_key,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.set_calls = []

    def get(self, key: str):
        return self.values.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.values[key] = value
        self.set_calls.append({"key": key, "ttl": ttl, "value": value})


def _payload() -> LLMCachePayload:
    return LLMCachePayload(
        question="Яка шкода від Fireball?",
        game_id="bg3",
        retrieval_query="Fireball damage",
        chunk_fingerprints=["Fireball:abc123"],
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        prompt_version="answer_v1",
        temperature=0,
    )


def test_build_llm_cache_key_is_stable_for_same_payload():
    first = build_llm_cache_key(_payload())
    second = build_llm_cache_key(_payload())

    assert first == second
    assert first.startswith("omnilibrarian:llm_response:v1:")


def test_redis_llm_cache_round_trips_answer_payload():
    redis = FakeRedis()
    cache = RedisLLMCache(redis_client=redis, ttl_seconds=60)
    payload = _payload()

    assert cache.get(payload) is None

    cache.set(payload, answer="Fireball завдає 8d6 шкоди [1].", sources=[{"id": 1, "title": "Fireball"}])

    cached = cache.get(payload)
    assert cached == {
        "answer": "Fireball завдає 8d6 шкоди [1].",
        "sources": [{"id": 1, "title": "Fireball"}],
    }
    assert redis.set_calls[0]["ttl"] == 60
