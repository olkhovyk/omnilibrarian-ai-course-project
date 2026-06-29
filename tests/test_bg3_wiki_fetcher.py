from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from uuid import uuid4

import httpx

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash
from omnilibrarian.ingestion.sources.bg3_wiki import BG3WikiFetcher, initial_bg3_wiki_manifest


HTML_PAGE = """
<!doctype html>
<html>
  <head><title>Fireball - bg3.wiki</title></head>
  <body>
    <nav>Navigation should not appear</nav>
    <main id="content">
      <h1 id="firstHeading">Fireball</h1>
      <div id="mw-content-text">
        <p><b>Fireball</b> is a level 3 evocation spell.</p>
        <p>It deals 8d6 Fire damage in a large area.</p>
        <span class="mw-editsection">edit</span>
      </div>
    </main>
  </body>
</html>
"""


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_fetcher_downloads_page_and_writes_raw_json():
    test_dir = _workspace_test_dir()
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            html=HTML_PAGE,
            headers={
                "etag": '"fireball-v1"',
                "last-modified": "Fri, 29 May 2026 09:00:00 GMT",
            },
        )

    cache = IngestionCache(test_dir / "cache.sqlite")
    fetcher = BG3WikiFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        now=lambda: datetime(2026, 5, 29, 9, 0, tzinfo=UTC),
    )
    ref = initial_bg3_wiki_manifest()[0]

    result = fetcher.fetch(ref)

    assert result.status == "fetched"
    assert len(requests) == 1
    assert result.raw_document.title == "Fireball"
    assert "level 3 evocation spell" in result.raw_document.text_en
    assert "Navigation should not appear" not in result.raw_document.text_en
    assert "edit" not in result.raw_document.text_en
    assert result.raw_path.exists()

    raw_json = json.loads(result.raw_path.read_text(encoding="utf-8"))
    assert raw_json["doc_id"] == "bg3_wiki:Fireball"
    assert raw_json["source_url"] == "https://bg3.wiki/wiki/Fireball"
    assert raw_json["text_en"] == result.raw_document.text_en

    entry = cache.get("bg3_wiki:Fireball")
    assert entry is not None
    assert entry.etag == '"fireball-v1"'
    assert entry.raw_path == str(result.raw_path)
    assert entry.content_hash == compute_content_hash(result.raw_document.text_en)


def test_fetcher_reuses_fresh_cache_without_http_request():
    test_dir = _workspace_test_dir()
    raw_path = test_dir / "raw" / "bg3" / "bg3_wiki" / "bg3_wiki_Fireball.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            {
                "doc_id": "bg3_wiki:Fireball",
                "game_id": "bg3",
                "source_id": "bg3_wiki",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "title": "Fireball",
                "text_en": "Fireball cached text.",
                "content_type": "spell",
                "fetched_at": "2026-05-29T09:00:00+00:00",
                "license": "CC BY-NC-SA 4.0 or CC BY-SA 4.0 where applicable",
            }
        ),
        encoding="utf-8",
    )
    cache = IngestionCache(test_dir / "cache.sqlite")
    cache.upsert_fetched(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        raw_path=str(raw_path),
        content_hash=compute_content_hash("Fireball cached text."),
        fetched_at=datetime(2026, 5, 29, 9, 0, tzinfo=UTC),
        checked_at=datetime(2026, 5, 29, 9, 0, tzinfo=UTC),
        status_code=200,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("fresh cache should skip HTTP")

    fetcher = BG3WikiFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        now=lambda: datetime(2026, 5, 29, 10, 0, tzinfo=UTC),
    )

    result = fetcher.fetch(initial_bg3_wiki_manifest()[0])

    assert result.status == "cached"
    assert result.raw_document.text_en == "Fireball cached text."


def test_fetcher_uses_conditional_headers_and_reuses_on_304():
    test_dir = _workspace_test_dir()
    raw_path = test_dir / "raw" / "bg3" / "bg3_wiki" / "bg3_wiki_Fireball.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            {
                "doc_id": "bg3_wiki:Fireball",
                "game_id": "bg3",
                "source_id": "bg3_wiki",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "title": "Fireball",
                "text_en": "Fireball old text.",
                "content_type": "spell",
                "fetched_at": "2026-05-01T09:00:00+00:00",
                "license": "CC BY-NC-SA 4.0 or CC BY-SA 4.0 where applicable",
            }
        ),
        encoding="utf-8",
    )
    cache = IngestionCache(test_dir / "cache.sqlite")
    cache.upsert_fetched(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        raw_path=str(raw_path),
        content_hash=compute_content_hash("Fireball old text."),
        fetched_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        checked_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        status_code=200,
        etag='"old-etag"',
        last_modified="Fri, 1 May 2026 09:00:00 GMT",
    )
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(304)

    fetcher = BG3WikiFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        now=lambda: datetime(2026, 5, 29, 9, 0, tzinfo=UTC),
    )

    result = fetcher.fetch(initial_bg3_wiki_manifest()[0], ttl_hours=1)

    assert result.status == "not_modified"
    assert seen_headers["if-none-match"] == '"old-etag"'
    assert seen_headers["if-modified-since"] == "Fri, 1 May 2026 09:00:00 GMT"
    assert result.raw_document.text_en == "Fireball old text."

    entry = cache.get("bg3_wiki:Fireball")
    assert entry is not None
    assert entry.status_code == 304
    assert entry.checked_at == datetime(2026, 5, 29, 9, 0, tzinfo=UTC)


def test_force_refresh_fetches_even_when_cache_is_fresh():
    test_dir = _workspace_test_dir()
    cache = IngestionCache(test_dir / "cache.sqlite")
    fetched_at = datetime(2026, 5, 29, 9, 0, tzinfo=UTC)
    cache.upsert_fetched(
        doc_id="bg3_wiki:Fireball",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        raw_path=str(test_dir / "raw.json"),
        content_hash=compute_content_hash("cached"),
        fetched_at=fetched_at,
        checked_at=fetched_at,
        status_code=200,
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, html=HTML_PAGE)

    fetcher = BG3WikiFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        now=lambda: fetched_at + timedelta(minutes=5),
    )

    result = fetcher.fetch(initial_bg3_wiki_manifest()[0], force_refresh=True)

    assert calls == 1
    assert result.status in {"fetched", "unchanged"}
