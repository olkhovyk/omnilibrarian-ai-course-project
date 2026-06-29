from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
import re
from pathlib import Path
import time
from urllib.parse import quote

import httpx

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash
from omnilibrarian.ingestion.documents import RawDocument, read_raw_document, write_raw_document
from omnilibrarian.ingestion.sources.base import SourceRef


BLUE_PRINCE_GAME_ID = "blue_prince"
BLUE_PRINCE_WIKI_SOURCE_ID = "blue_prince_wiki"
BLUE_PRINCE_WIKI_BASE_URL = "https://blueprince.wiki.gg/wiki"
BLUE_PRINCE_WIKI_API_URLS = (
    "https://blueprince.wiki.gg/api.php",
    "https://blueprince.wiki.gg/w/api.php",
)
BLUE_PRINCE_WIKI_LICENSE = "CC BY-SA 4.0 unless otherwise noted"

BLUE_PRINCE_WIKI_CONTENT_TYPES = {
    "rooms",
    "items",
    "mechanics",
    "puzzles",
    "progression",
    "lore",
}

BLUE_PRINCE_WIKI_DEFAULT_CATEGORIES = [
    "rooms",
    "mechanics",
    "items",
    "puzzles",
    "progression",
    "lore",
]

BLUE_PRINCE_WIKI_SEED_PAGES = {
    "rooms": [
        "Rooms",
        "Category:Rooms",
        "Parlor",
        "Billiard_Room",
        "Bedroom",
        "Drafting_Studio",
        "Vault",
        "Room_46",
    ],
    "mechanics": [
        "Blueprints",
        "Room_shape",
        "Mechanical_Rooms",
        "Entry_Rooms",
        "Spread_Rooms",
        "Outer_Rooms",
    ],
    "items": [
        "Items",
    ],
    "puzzles": [
        "Puzzles",
    ],
    "progression": [
        "Walkthrough",
    ],
    "lore": [
        "Lore",
    ],
}


@dataclass(frozen=True)
class FetchResult:
    status: str
    raw_document: RawDocument
    raw_path: Path


class BluePrinceWikiFetcher:
    def __init__(
        self,
        *,
        cache: IngestionCache,
        raw_root: str | Path,
        http_client: httpx.Client | None = None,
        now=None,
        request_delay_seconds: float = 0.5,
        max_retries: int = 3,
        retry_backoff_seconds: float = 5.0,
        sleeper=time.sleep,
    ) -> None:
        self.cache = cache
        self.raw_root = Path(raw_root)
        self.http_client = http_client or httpx.Client(
            timeout=20.0,
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

        headers = {} if force_refresh else self._conditional_headers(entry)
        response = self._get_article(ref.source_url, headers=headers)
        raw_path = self._raw_path(ref)

        if response.status_code == 304 and entry is not None:
            self.cache.mark_not_modified(ref.doc_id, checked_at=now)
            existing_path = Path(entry.raw_path)
            return FetchResult(
                status="not_modified",
                raw_document=read_raw_document(existing_path),
                raw_path=existing_path,
            )

        response.raise_for_status()
        text_en = extract_blue_prince_wiki_text(response.text)
        raw_document = RawDocument(
            doc_id=ref.doc_id,
            game_id=BLUE_PRINCE_GAME_ID,
            source_id=BLUE_PRINCE_WIKI_SOURCE_ID,
            source_url=ref.source_url,
            title=ref.title,
            text_en=text_en,
            content_type=ref.content_type,
            fetched_at=now.isoformat(),
            license=BLUE_PRINCE_WIKI_LICENSE,
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

    def discover_all_pages_manifest(self, *, max_documents: int | None = None) -> list[SourceRef]:
        return discover_blue_prince_wiki_all_pages_manifest(http_client=self.http_client, max_documents=max_documents)

    def _get_article(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            self._sleep_before_request()
            response = self.http_client.get(url, headers=headers)
            if response.status_code != 429:
                return response
            if attempt >= self.max_retries:
                return response
            self._sleep_after_rate_limit(response=response, attempt=attempt)
        return response

    def _sleep_before_request(self) -> None:
        if self.request_delay_seconds > 0:
            self._sleeper(self.request_delay_seconds)

    def _sleep_after_rate_limit(self, *, response: httpx.Response, attempt: int) -> None:
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        delay = retry_after if retry_after is not None else self.retry_backoff_seconds * (attempt + 1)
        if delay > 0:
            self._sleeper(delay)

    def _raw_path(self, ref: SourceRef) -> Path:
        safe_doc_id = ref.doc_id.replace(":", "_").replace("/", "_")
        return self.raw_root / BLUE_PRINCE_GAME_ID / BLUE_PRINCE_WIKI_SOURCE_ID / f"{safe_doc_id}.json"

    def _conditional_headers(self, entry) -> dict[str, str]:
        if entry is None:
            return {}

        headers: dict[str, str] = {}
        if entry.etag:
            headers["if-none-match"] = entry.etag
        if entry.last_modified:
            headers["if-modified-since"] = entry.last_modified
        return headers


def build_blue_prince_wiki_seed_manifest(
    *,
    categories: list[str] | None = None,
    max_documents: int | None = None,
) -> list[SourceRef]:
    selected_categories = categories or list(BLUE_PRINCE_WIKI_SEED_PAGES)
    refs: list[SourceRef] = []
    for category in selected_categories:
        if category not in BLUE_PRINCE_WIKI_SEED_PAGES:
            raise ValueError(f"Unknown Blue Prince wiki category: {category}")
        for page in BLUE_PRINCE_WIKI_SEED_PAGES[category]:
            refs.append(_page_to_source_ref(page=page, content_type=category))
            if max_documents is not None and len(refs) >= max_documents:
                return refs
    return refs


def _page_to_source_ref(*, page: str, content_type: str) -> SourceRef:
    title = page.replace("_", " ")
    return SourceRef(
        doc_id=f"{BLUE_PRINCE_WIKI_SOURCE_ID}:{page}",
        source_url=f"{BLUE_PRINCE_WIKI_BASE_URL}/{quote(page, safe=':')}",
        title=title,
        content_type=content_type,
    )


def discover_blue_prince_wiki_all_pages_manifest(
    *,
    http_client: httpx.Client,
    max_documents: int | None = None,
) -> list[SourceRef]:
    last_error: Exception | None = None
    for api_url in BLUE_PRINCE_WIKI_API_URLS:
        try:
            return _discover_all_pages_from_api(
                http_client=http_client,
                api_url=api_url,
                max_documents=max_documents,
            )
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code not in {403, 404, 405}:
                raise
        except (httpx.RequestError, ValueError) as exc:
            last_error = exc
    raise RuntimeError("Could not discover Blue Prince wiki pages through known API endpoints.") from last_error


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def _discover_all_pages_from_api(
    *,
    http_client: httpx.Client,
    api_url: str,
    max_documents: int | None,
) -> list[SourceRef]:
    refs: list[SourceRef] = []
    gapcontinue = None
    while max_documents is None or len(refs) < max_documents:
        params = {
            "action": "query",
            "generator": "allpages",
            "gapnamespace": "0",
            "gapfilterredir": "nonredirects",
            "gaplimit": "500",
            "prop": "categories",
            "cllimit": "max",
            "format": "json",
            "formatversion": "2",
        }
        if gapcontinue:
            params["gapcontinue"] = gapcontinue

        response = http_client.get(api_url, params=params)
        response.raise_for_status()
        payload = response.json()
        pages = payload.get("query", {}).get("pages", [])
        if not pages:
            break

        for page in pages:
            title = str(page.get("title") or "")
            if not title or _should_skip_title(title):
                continue
            category_titles = [str(category.get("title") or "") for category in page.get("categories", [])]
            refs.append(_page_title_to_source_ref(title=title, category_titles=category_titles))
            if max_documents is not None and len(refs) >= max_documents:
                return _dedupe_refs(refs)

        gapcontinue = payload.get("continue", {}).get("gapcontinue")
        if not gapcontinue:
            break
    return _dedupe_refs(refs)


def _page_title_to_source_ref(*, title: str, category_titles: list[str]) -> SourceRef:
    page = title.replace(" ", "_")
    return SourceRef(
        doc_id=f"{BLUE_PRINCE_WIKI_SOURCE_ID}:{page}",
        source_url=f"{BLUE_PRINCE_WIKI_BASE_URL}/{quote(page, safe=':')}",
        title=title,
        content_type=_infer_content_type(title=title, category_titles=category_titles),
    )


def _infer_content_type(*, title: str, category_titles: list[str]) -> str:
    haystack = " ".join([title, *category_titles]).casefold()
    if "room" in haystack or "floorplan" in haystack:
        return "rooms"
    if "item" in haystack or "key" in haystack or "resource" in haystack:
        return "items"
    if "puzzle" in haystack or "safe" in haystack or "chess" in haystack:
        return "puzzles"
    if "lore" in haystack or "story" in haystack or "character" in haystack:
        return "lore"
    if "ending" in haystack or "walkthrough" in haystack or "progression" in haystack:
        return "progression"
    return "mechanics"


def _should_skip_title(title: str) -> bool:
    lowered = title.casefold()
    return lowered.startswith(
        (
            "file:",
            "template:",
            "category:",
            "module:",
            "user:",
            "wiki.gg:",
            "blue prince wiki",
        )
    )


def _dedupe_refs(refs: list[SourceRef]) -> list[SourceRef]:
    seen: set[str] = set()
    deduped: list[SourceRef] = []
    for ref in refs:
        if ref.doc_id in seen:
            continue
        seen.add(ref.doc_id)
        deduped.append(ref)
    return deduped


class _WikiTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture_depth = 0
        self._skip_depth = 0
        self._pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        element_id = attrs_dict.get("id", "")
        class_name = attrs_dict.get("class", "")

        if element_id == "mw-content-text":
            self._capture_depth = 1
            return

        if self._capture_depth:
            self._capture_depth += 1
            if tag in {"script", "style", "sup"} or "mw-editsection" in class_name:
                self._skip_depth += 1
            if tag in {"p", "li", "h2", "h3", "h4", "tr", "br"}:
                self._pieces.append("\n")
            if tag in {"td", "th"}:
                self._pieces.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        if self._skip_depth:
            self._skip_depth -= 1
        self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth and not self._skip_depth:
            text = data.strip()
            if text:
                self._pieces.append(f"{text} ")

    def text(self) -> str:
        raw = "".join(self._pieces)
        lines = []
        for line in raw.splitlines():
            clean_line = re.sub(r"\s+", " ", line).strip(" |")
            if clean_line:
                lines.append(clean_line)
        return "\n".join(lines).strip()


def extract_blue_prince_wiki_text(html: str) -> str:
    parser = _WikiTextParser()
    parser.feed(html)
    text = parser.text()
    if not text:
        raise ValueError("Could not extract article text from Blue Prince wiki HTML.")
    return text
