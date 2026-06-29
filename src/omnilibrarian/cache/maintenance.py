from __future__ import annotations

from dataclasses import dataclass

from omnilibrarian.cache.llm_cache import CACHE_PREFIX


@dataclass(frozen=True)
class CacheClearResult:
    pattern: str
    matched: int
    deleted: int
    dry_run: bool


def clear_redis_keys(*, redis_client, pattern: str, dry_run: bool = True, batch_size: int = 500) -> CacheClearResult:
    matched = 0
    deleted = 0
    batch: list[str] = []

    for key in redis_client.scan_iter(match=pattern, count=batch_size):
        matched += 1
        batch.append(key)
        if len(batch) >= batch_size:
            deleted += _delete_batch(redis_client=redis_client, keys=batch, dry_run=dry_run)
            batch = []

    if batch:
        deleted += _delete_batch(redis_client=redis_client, keys=batch, dry_run=dry_run)

    return CacheClearResult(pattern=pattern, matched=matched, deleted=deleted, dry_run=dry_run)


def llm_cache_pattern() -> str:
    return f"{CACHE_PREFIX}:*"


def _delete_batch(*, redis_client, keys: list, dry_run: bool) -> int:
    if dry_run or not keys:
        return 0
    return int(redis_client.delete(*keys))
