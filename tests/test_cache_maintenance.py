from omnilibrarian.cache.llm_cache import CACHE_PREFIX
from omnilibrarian.cache.maintenance import clear_redis_keys, llm_cache_pattern


class FakeRedis:
    def __init__(self, keys: list[str]) -> None:
        self.keys = set(keys)
        self.deleted_batches = []

    def scan_iter(self, match: str, count: int = 500):
        prefix = match.removesuffix("*")
        for key in sorted(self.keys):
            if key.startswith(prefix):
                yield key

    def delete(self, *keys) -> int:
        self.deleted_batches.append(keys)
        deleted = 0
        for key in keys:
            if key in self.keys:
                self.keys.remove(key)
                deleted += 1
        return deleted


def test_llm_cache_pattern_is_scoped_to_omnilibrarian_llm_responses():
    assert llm_cache_pattern() == f"{CACHE_PREFIX}:*"


def test_clear_redis_keys_dry_run_counts_without_deleting():
    redis = FakeRedis(
        [
            f"{CACHE_PREFIX}:a",
            f"{CACHE_PREFIX}:b",
            "unrelated:key",
        ]
    )

    result = clear_redis_keys(redis_client=redis, pattern=llm_cache_pattern(), dry_run=True, batch_size=1)

    assert result.matched == 2
    assert result.deleted == 0
    assert result.dry_run is True
    assert f"{CACHE_PREFIX}:a" in redis.keys
    assert redis.deleted_batches == []


def test_clear_redis_keys_apply_deletes_only_matched_keys():
    redis = FakeRedis(
        [
            f"{CACHE_PREFIX}:a",
            f"{CACHE_PREFIX}:b",
            "unrelated:key",
        ]
    )

    result = clear_redis_keys(redis_client=redis, pattern=llm_cache_pattern(), dry_run=False, batch_size=2)

    assert result.matched == 2
    assert result.deleted == 2
    assert redis.keys == {"unrelated:key"}
