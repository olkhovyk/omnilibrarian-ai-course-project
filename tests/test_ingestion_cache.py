from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash


def _cache_db_path() -> Path:
    cache_dir = Path(".test_cache")
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{uuid4()}.sqlite"


def test_cache_stores_and_loads_fetch_metadata():
    cache = IngestionCache(_cache_db_path())
    fetched_at = datetime(2026, 5, 29, 9, 0, tzinfo=UTC)

    cache.upsert_fetched(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        raw_path="data/raw/bg3/bg3_wiki/bg3_wiki_Fireball.json",
        content_hash="sha256:abc",
        fetched_at=fetched_at,
        checked_at=fetched_at,
        status_code=200,
        etag='"v1"',
        last_modified="Fri, 29 May 2026 09:00:00 GMT",
    )

    entry = cache.get("bg3_wiki:Fireball")

    assert entry is not None
    assert entry.game_id == "bg3"
    assert entry.source_id == "bg3_wiki"
    assert entry.content_hash == "sha256:abc"
    assert entry.etag == '"v1"'
    assert cache.is_fresh(entry, now=fetched_at + timedelta(hours=1), ttl_hours=168)


def test_cache_marks_old_entries_as_stale():
    cache = IngestionCache(_cache_db_path())
    fetched_at = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

    cache.upsert_fetched(
        doc_id="bg3_wiki:Wizard",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Wizard",
        raw_path="data/raw/bg3/bg3_wiki/bg3_wiki_Wizard.json",
        content_hash="sha256:def",
        fetched_at=fetched_at,
        checked_at=fetched_at,
        status_code=200,
    )

    entry = cache.get("bg3_wiki:Wizard")

    assert entry is not None
    assert not cache.is_fresh(entry, now=datetime(2026, 5, 29, 9, 0, tzinfo=UTC), ttl_hours=168)


def test_not_modified_refresh_updates_checked_at_without_changing_hash():
    cache = IngestionCache(_cache_db_path())
    fetched_at = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    checked_at = datetime(2026, 5, 29, 9, 0, tzinfo=UTC)

    cache.upsert_fetched(
        doc_id="bg3_wiki:Haste",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Haste",
        raw_path="data/raw/bg3/bg3_wiki/bg3_wiki_Haste.json",
        content_hash="sha256:ghi",
        fetched_at=fetched_at,
        checked_at=fetched_at,
        status_code=200,
    )

    cache.mark_not_modified("bg3_wiki:Haste", checked_at=checked_at)
    entry = cache.get("bg3_wiki:Haste")

    assert entry is not None
    assert entry.content_hash == "sha256:ghi"
    assert entry.fetched_at == fetched_at
    assert entry.checked_at == checked_at
    assert entry.status_code == 304


def test_content_hash_is_stable_for_same_text():
    assert compute_content_hash("Fireball deals 8d6 fire damage.") == compute_content_hash(
        "Fireball deals 8d6 fire damage."
    )
    assert compute_content_hash("Fireball deals 8d6 fire damage.") != compute_content_hash(
        "Magic Missile creates three darts."
    )
