from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class CacheEntry:
    doc_id: str
    game_id: str
    source_id: str
    source_url: str
    raw_path: str
    content_hash: str
    fetched_at: datetime
    checked_at: datetime
    status_code: int
    etag: str | None = None
    last_modified: str | None = None


def compute_content_hash(text: str) -> str:
    digest = sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class IngestionCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get(self, doc_id: str) -> CacheEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    doc_id,
                    game_id,
                    source_id,
                    source_url,
                    raw_path,
                    content_hash,
                    fetched_at,
                    checked_at,
                    status_code,
                    etag,
                    last_modified
                FROM source_cache
                WHERE doc_id = ?
                """,
                (doc_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_entry(row)

    def upsert_fetched(
        self,
        *,
        doc_id: str,
        game_id: str,
        source_id: str,
        source_url: str,
        raw_path: str,
        content_hash: str,
        fetched_at: datetime,
        checked_at: datetime,
        status_code: int,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_cache (
                    doc_id,
                    game_id,
                    source_id,
                    source_url,
                    raw_path,
                    content_hash,
                    fetched_at,
                    checked_at,
                    status_code,
                    etag,
                    last_modified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    game_id = excluded.game_id,
                    source_id = excluded.source_id,
                    source_url = excluded.source_url,
                    raw_path = excluded.raw_path,
                    content_hash = excluded.content_hash,
                    fetched_at = excluded.fetched_at,
                    checked_at = excluded.checked_at,
                    status_code = excluded.status_code,
                    etag = excluded.etag,
                    last_modified = excluded.last_modified
                """,
                (
                    doc_id,
                    game_id,
                    source_id,
                    source_url,
                    raw_path,
                    content_hash,
                    self._format_datetime(fetched_at),
                    self._format_datetime(checked_at),
                    status_code,
                    etag,
                    last_modified,
                ),
            )

    def mark_not_modified(self, doc_id: str, *, checked_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE source_cache
                SET checked_at = ?, status_code = 304
                WHERE doc_id = ?
                """,
                (self._format_datetime(checked_at), doc_id),
            )

    def is_fresh(self, entry: CacheEntry, *, now: datetime, ttl_hours: int) -> bool:
        age_seconds = (self._ensure_utc(now) - entry.checked_at).total_seconds()
        return age_seconds < ttl_hours * 60 * 60

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_cache (
                    doc_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    raw_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    etag TEXT,
                    last_modified TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source_cache_game_source
                ON source_cache(game_id, source_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _row_to_entry(self, row: tuple) -> CacheEntry:
        return CacheEntry(
            doc_id=row[0],
            game_id=row[1],
            source_id=row[2],
            source_url=row[3],
            raw_path=row[4],
            content_hash=row[5],
            fetched_at=self._parse_datetime(row[6]),
            checked_at=self._parse_datetime(row[7]),
            status_code=row[8],
            etag=row[9],
            last_modified=row[10],
        )

    def _format_datetime(self, value: datetime) -> str:
        return self._ensure_utc(value).isoformat()

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return self._ensure_utc(parsed)

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
