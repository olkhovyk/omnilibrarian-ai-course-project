from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

import httpx

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash
from omnilibrarian.ingestion.sources.blue_prince_wiki import (
    BLUE_PRINCE_WIKI_API_URLS,
    BluePrinceWikiFetcher,
    build_blue_prince_wiki_seed_manifest,
    discover_blue_prince_wiki_all_pages_manifest,
    extract_blue_prince_wiki_text,
)


HTML_PAGE = """
<!doctype html>
<html>
  <body>
    <nav>Navigation should not appear</nav>
    <div id="mw-content-text">
      <p><b>Parlor</b> is a puzzle room in Blue Prince.</p>
      <table>
        <tr><th>Room</th><th>Type</th></tr>
        <tr><td>Parlor</td><td>Puzzle</td></tr>
      </table>
      <span class="mw-editsection">edit</span>
    </div>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, headers: dict | None = None) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://blueprince.wiki.gg/api.php")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self) -> dict:
        return self.payload


class FakeHTTPClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls = []

    def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self.responses.pop(0)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_extract_blue_prince_wiki_text_keeps_table_text_and_drops_navigation():
    text = extract_blue_prince_wiki_text(HTML_PAGE)

    assert "Parlor is a puzzle room" in text
    assert "Room | Type" in text
    assert "Parlor | Puzzle" in text
    assert "Navigation should not appear" not in text
    assert "edit" not in text


def test_fetcher_downloads_page_and_writes_blue_prince_raw_json():
    test_dir = _workspace_test_dir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=HTML_PAGE, headers={"etag": '"parlor-v1"'})

    cache = IngestionCache(test_dir / "cache.sqlite")
    fetcher = BluePrinceWikiFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        now=lambda: datetime(2026, 6, 6, 10, 0, tzinfo=UTC),
    )
    ref = build_blue_prince_wiki_seed_manifest(categories=["rooms"], max_documents=3)[2]

    result = fetcher.fetch(ref)

    assert result.status == "fetched"
    assert result.raw_document.game_id == "blue_prince"
    assert result.raw_document.source_id == "blue_prince_wiki"
    assert result.raw_document.title == "Parlor"
    assert "Parlor is a puzzle room" in result.raw_document.text_en
    assert result.raw_path.exists()

    raw_json = json.loads(result.raw_path.read_text(encoding="utf-8"))
    assert raw_json["doc_id"] == "blue_prince_wiki:Parlor"
    assert raw_json["source_url"] == "https://blueprince.wiki.gg/wiki/Parlor"

    entry = cache.get("blue_prince_wiki:Parlor")
    assert entry is not None
    assert entry.game_id == "blue_prince"
    assert entry.source_id == "blue_prince_wiki"
    assert entry.content_hash == compute_content_hash(result.raw_document.text_en)


def test_fetcher_retries_rate_limited_article_requests_with_retry_after_delay():
    test_dir = _workspace_test_dir()
    sleep_calls = []
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "2"}, request=request)
        return httpx.Response(200, html=HTML_PAGE, request=request)

    fetcher = BluePrinceWikiFetcher(
        cache=IngestionCache(test_dir / "cache.sqlite"),
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        request_delay_seconds=0.25,
        max_retries=2,
        retry_backoff_seconds=10.0,
        sleeper=sleep_calls.append,
        now=lambda: datetime(2026, 6, 6, 10, 0, tzinfo=UTC),
    )
    ref = build_blue_prince_wiki_seed_manifest(categories=["rooms"], max_documents=3)[2]

    result = fetcher.fetch(ref)

    assert result.status == "fetched"
    assert len(calls) == 2
    assert sleep_calls == [0.25, 2.0, 0.25]


def test_all_pages_manifest_discovers_pages_and_infers_content_types():
    client = FakeHTTPClient(
        [
            FakeResponse(
                {
                    "query": {
                        "pages": [
                            {
                                "title": "Parlor",
                                "categories": [{"title": "Category:Rooms"}],
                            },
                            {
                                "title": "Safe puzzle",
                                "categories": [{"title": "Category:Puzzles"}],
                            },
                            {
                                "title": "Blue Prince Wiki/contribute",
                                "categories": [],
                            },
                            {
                                "title": "Template:Hidden",
                                "categories": [],
                            },
                        ]
                    }
                }
            )
        ]
    )

    manifest = discover_blue_prince_wiki_all_pages_manifest(http_client=client)

    assert [ref.title for ref in manifest] == ["Parlor", "Safe puzzle"]
    assert [ref.content_type for ref in manifest] == ["rooms", "puzzles"]
    assert manifest[0].source_url == "https://blueprince.wiki.gg/wiki/Parlor"
    assert client.calls[0]["url"] == BLUE_PRINCE_WIKI_API_URLS[0]
    assert client.calls[0]["params"]["generator"] == "allpages"


def test_all_pages_manifest_falls_back_to_second_api_endpoint():
    client = FakeHTTPClient(
        [
            FakeResponse({}, status_code=404),
            FakeResponse({"query": {"pages": [{"title": "Rooms", "categories": []}]}}, status_code=200),
        ]
    )

    manifest = discover_blue_prince_wiki_all_pages_manifest(http_client=client)

    assert [call["url"] for call in client.calls] == list(BLUE_PRINCE_WIKI_API_URLS)
    assert manifest[0].title == "Rooms"
