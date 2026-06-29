from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash
from omnilibrarian.ingestion.documents import RawDocument, read_raw_document, write_raw_document
from omnilibrarian.ingestion.sources.base import SourceRef


BLUE_PRINCE_GAME_ID = "blue_prince"
BLUE_PRINCE_REDDIT_SOURCE_ID = "blue_prince_reddit"
BLUE_PRINCE_SUBREDDIT_URL = "https://www.reddit.com/r/BluePrince/"
BLUE_PRINCE_REDDIT_LICENSE = "User-generated Reddit content; store permalink attribution"
BLUE_PRINCE_REDDIT_CURATED_POST_URLS = [
    "https://www.reddit.com/r/BluePrince/comments/1n0wdv6/megathread_v3_post_and_ask_hints_for_puzzles_here/",
    "https://www.reddit.com/r/BluePrince/comments/1sywuti/blue_prince_patch_17_the_accessibility_update/",
]


@dataclass(frozen=True)
class FetchResult:
    status: str
    raw_document: RawDocument
    raw_path: Path


class BluePrinceRedditFetcher:
    def __init__(
        self,
        *,
        cache: IngestionCache,
        raw_root: str | Path,
        http_client: httpx.Client | None = None,
        now=None,
        request_delay_seconds: float = 1.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 10.0,
        sleeper=time.sleep,
    ) -> None:
        self.cache = cache
        self.raw_root = Path(raw_root)
        self.http_client = http_client or httpx.Client(
            timeout=30.0,
            headers={"user-agent": "OmniLibrarianCourseProject/0.1"},
            follow_redirects=True,
        )
        self._now = now or (lambda: datetime.now(UTC))
        self.request_delay_seconds = request_delay_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._sleeper = sleeper

    def fetch(self, ref: SourceRef, *, ttl_hours: int = 168, force_refresh: bool = False) -> FetchResult:
        now = self._now()
        entry = self.cache.get(ref.doc_id)
        if entry and not force_refresh and self.cache.is_fresh(entry, now=now, ttl_hours=ttl_hours):
            raw_path = Path(entry.raw_path)
            return FetchResult(status="cached", raw_document=read_raw_document(raw_path), raw_path=raw_path)

        response = self._get_json(_reddit_json_url(ref.source_url))
        raw_path = self._raw_path(ref)
        if response.status_code >= 400:
            if entry:
                cached_raw_path = Path(entry.raw_path)
                if cached_raw_path.exists():
                    return FetchResult(
                        status=f"cached_stale_http_{response.status_code}",
                        raw_document=read_raw_document(cached_raw_path),
                        raw_path=cached_raw_path,
                    )
            response.raise_for_status()
        reddit_post = extract_reddit_post_text(response.json())
        title = reddit_post["title"] or ref.title
        raw_document = RawDocument(
            doc_id=ref.doc_id,
            game_id=BLUE_PRINCE_GAME_ID,
            source_id=BLUE_PRINCE_REDDIT_SOURCE_ID,
            source_url=ref.source_url,
            title=title,
            text_en=json.dumps(reddit_post, ensure_ascii=False),
            content_type=ref.content_type,
            fetched_at=now.isoformat(),
            license=BLUE_PRINCE_REDDIT_LICENSE,
        )
        content_hash = compute_content_hash(raw_document.text_en)
        status = "unchanged" if entry and entry.content_hash == content_hash else "fetched"
        write_raw_document(raw_path, raw_document)
        self.cache.upsert_fetched(
            doc_id=raw_document.doc_id,
            game_id=raw_document.game_id,
            source_id=raw_document.source_id,
            source_url=raw_document.source_url,
            raw_path=str(raw_path),
            content_hash=content_hash,
            fetched_at=now,
            checked_at=now,
            status_code=response.status_code,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        return FetchResult(status=status, raw_document=raw_document, raw_path=raw_path)

    def _raw_path(self, ref: SourceRef) -> Path:
        safe_doc_id = ref.doc_id.replace(":", "_").replace("/", "_")
        return self.raw_root / BLUE_PRINCE_GAME_ID / BLUE_PRINCE_REDDIT_SOURCE_ID / f"{safe_doc_id}.json"

    def _get_json(self, url: str) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            if self.request_delay_seconds > 0:
                self._sleeper(self.request_delay_seconds)
            response = self.http_client.get(url)
            if response.status_code != 429:
                return response
            if attempt >= self.max_retries:
                return response
            retry_after = _parse_retry_after(response.headers.get("retry-after"))
            delay = retry_after if retry_after is not None else self.retry_backoff_seconds * (attempt + 1)
            if delay > 0:
                self._sleeper(delay)
        return response


def build_blue_prince_reddit_manifest(post_urls: list[str] | None = None) -> list[SourceRef]:
    post_urls = post_urls or BLUE_PRINCE_REDDIT_CURATED_POST_URLS
    refs: list[SourceRef] = []
    for url in post_urls:
        if "/r/BluePrince/" not in url:
            raise ValueError(f"Reddit URL is not from r/BluePrince: {url}")
        slug = _reddit_slug(url)
        content_type = "patch_note" if "patch" in slug else "community_tip"
        refs.append(
            SourceRef(
                doc_id=f"{BLUE_PRINCE_REDDIT_SOURCE_ID}:{slug}",
                source_url=url,
                title=slug.replace("_", " ").strip(),
                content_type=content_type,
            )
        )
    return refs


def extract_reddit_post_text(payload: object, *, max_comments: int = 20) -> dict:
    if not isinstance(payload, list) or len(payload) < 1:
        raise ValueError("Expected Reddit post JSON listing.")

    post_listing = payload[0]
    post_children = post_listing.get("data", {}).get("children", []) if isinstance(post_listing, dict) else []
    if not post_children:
        raise ValueError("Reddit post JSON did not include a post.")
    post_data = post_children[0].get("data", {})

    comments: list[dict] = []
    if len(payload) > 1 and isinstance(payload[1], dict):
        comment_children = payload[1].get("data", {}).get("children", [])
        for child in comment_children:
            if child.get("kind") != "t1":
                continue
            data = child.get("data", {})
            body = _clean_reddit_text(str(data.get("body") or ""))
            if not body or body in {"[deleted]", "[removed]"}:
                continue
            comments.append(
                {
                    "author": str(data.get("author") or "unknown"),
                    "score": int(data.get("score") or 0),
                    "body": body,
                    "permalink": f"https://www.reddit.com{data.get('permalink') or ''}",
                }
            )
            if len(comments) >= max_comments:
                break

    return {
        "title": str(post_data.get("title") or ""),
        "author": str(post_data.get("author") or "unknown"),
        "score": int(post_data.get("score") or 0),
        "selftext": _clean_reddit_text(str(post_data.get("selftext") or "")),
        "permalink": f"https://www.reddit.com{post_data.get('permalink') or ''}",
        "comments": comments,
    }


def _reddit_slug(url: str) -> str:
    match = re.search(r"/comments/([^/]+)/([^/?#]+)", url)
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_").lower()
    return cleaned[-120:] or "reddit_post"


def _reddit_json_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    return urlunsplit((parts.scheme, parts.netloc, path, "limit=20&sort=top", ""))


def _clean_reddit_text(text: str) -> str:
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None
