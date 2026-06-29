from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Protocol


PROMPT_VERSION = "answer_v2"
CACHE_PREFIX = "omnilibrarian:llm_response:v1"


@dataclass(frozen=True)
class LLMCachePayload:
    question: str
    game_id: str
    retrieval_query: str
    chunk_fingerprints: list[str]
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION
    temperature: int = 0


class LLMCache(Protocol):
    def get(self, payload: LLMCachePayload) -> dict | None:
        ...

    def set(self, payload: LLMCachePayload, *, answer: str, sources: list[dict]) -> None:
        ...


class RedisLLMCache:
    def __init__(self, *, redis_client, ttl_seconds: int) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def get(self, payload: LLMCachePayload) -> dict | None:
        raw_value = self.redis_client.get(build_llm_cache_key(payload))
        if raw_value is None:
            return None
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        data = json.loads(raw_value)
        return {
            "answer": data["answer"],
            "sources": data["sources"],
        }

    def set(self, payload: LLMCachePayload, *, answer: str, sources: list[dict]) -> None:
        value = {
            "answer": answer,
            "sources": sources,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cache_key_payload": asdict(payload),
        }
        self.redis_client.setex(
            build_llm_cache_key(payload),
            self.ttl_seconds,
            json.dumps(value, ensure_ascii=False),
        )


class NullLLMCache:
    def get(self, payload: LLMCachePayload) -> dict | None:
        return None

    def set(self, payload: LLMCachePayload, *, answer: str, sources: list[dict]) -> None:
        return None


def build_llm_cache_key(payload: LLMCachePayload) -> str:
    encoded = json.dumps(asdict(payload), ensure_ascii=False, sort_keys=True)
    digest = sha256(encoded.encode("utf-8")).hexdigest()
    return f"{CACHE_PREFIX}:{digest}"


def build_redis_llm_cache(*, redis_url: str, ttl_seconds: int) -> RedisLLMCache:
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("redis package is required for RedisLLMCache.") from exc
    return RedisLLMCache(redis_client=Redis.from_url(redis_url), ttl_seconds=ttl_seconds)
