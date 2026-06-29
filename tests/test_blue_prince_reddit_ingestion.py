from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

import httpx

from omnilibrarian.ingestion.cache import IngestionCache
from omnilibrarian.ingestion.normalize import process_raw_documents_to_chunks
from omnilibrarian.ingestion.sources.blue_prince_reddit import (
    BluePrinceRedditFetcher,
    build_blue_prince_reddit_manifest,
    extract_reddit_post_text,
)
from omnilibrarian.ingestion.sources.blue_prince_reddit_normalizer import BluePrinceRedditNormalizer


REDDIT_PAYLOAD = [
    {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "title": "Megathread: post and ask hints for puzzles here",
                        "author": "mod",
                        "score": 123,
                        "selftext": "Use this thread for puzzle hints, not direct spoilers.",
                        "permalink": "/r/BluePrince/comments/abc123/example_hint_thread/",
                    },
                }
            ]
        }
    },
    {
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "author": "player1",
                        "score": 42,
                        "body": "For the Parlor puzzle, look at the note first.",
                        "permalink": "/r/BluePrince/comments/abc123/comment1/",
                    },
                },
                {"kind": "more", "data": {}},
            ]
        }
    },
]


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_extract_reddit_post_text_keeps_post_and_top_comments():
    extracted = extract_reddit_post_text(REDDIT_PAYLOAD)

    assert extracted["title"] == "Megathread: post and ask hints for puzzles here"
    assert extracted["selftext"] == "Use this thread for puzzle hints, not direct spoilers."
    assert extracted["comments"][0]["body"] == "For the Parlor puzzle, look at the note first."
    assert extracted["comments"][0]["permalink"].startswith("https://www.reddit.com/r/BluePrince/")


def test_reddit_fetcher_downloads_json_and_writes_raw_document():
    test_dir = _workspace_test_dir()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith(".json?limit=20&sort=top")
        return httpx.Response(200, json=REDDIT_PAYLOAD, request=request)

    fetcher = BluePrinceRedditFetcher(
        cache=IngestionCache(test_dir / "cache.sqlite"),
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        request_delay_seconds=0,
        now=lambda: datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )
    ref = build_blue_prince_reddit_manifest(
        ["https://www.reddit.com/r/BluePrince/comments/abc123/example_hint_thread/"]
    )[0]

    result = fetcher.fetch(ref)

    assert result.status == "fetched"
    assert result.raw_document.game_id == "blue_prince"
    assert result.raw_document.source_id == "blue_prince_reddit"
    assert result.raw_document.title == "Megathread: post and ask hints for puzzles here"
    assert result.raw_path.exists()
    raw_json = json.loads(result.raw_path.read_text(encoding="utf-8"))
    assert "Parlor puzzle" in raw_json["text_en"]


def test_reddit_fetcher_uses_stale_cache_when_reddit_blocks_refresh():
    test_dir = _workspace_test_dir()
    cache = IngestionCache(test_dir / "cache.sqlite")
    ref = build_blue_prince_reddit_manifest(
        ["https://www.reddit.com/r/BluePrince/comments/abc123/example_hint_thread/"]
    )[0]

    def success_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=REDDIT_PAYLOAD, request=request)

    first_fetcher = BluePrinceRedditFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(success_handler),
        request_delay_seconds=0,
        now=lambda: datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )
    first_result = first_fetcher.fetch(ref)

    def blocked_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Blocked", request=request)

    second_fetcher = BluePrinceRedditFetcher(
        cache=cache,
        raw_root=test_dir / "raw",
        http_client=_client(blocked_handler),
        request_delay_seconds=0,
        now=lambda: datetime(2026, 6, 11, 10, 0, tzinfo=UTC),
    )

    second_result = second_fetcher.fetch(ref, force_refresh=True)

    assert second_result.status == "cached_stale_http_403"
    assert second_result.raw_path == first_result.raw_path
    assert second_result.raw_document.title == "Megathread: post and ask hints for puzzles here"


def test_reddit_normalizer_writes_community_tip_chunks():
    test_dir = _workspace_test_dir()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=REDDIT_PAYLOAD, request=request)

    fetcher = BluePrinceRedditFetcher(
        cache=IngestionCache(test_dir / "cache.sqlite"),
        raw_root=test_dir / "raw",
        http_client=_client(handler),
        request_delay_seconds=0,
        now=lambda: datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )
    ref = build_blue_prince_reddit_manifest(
        ["https://www.reddit.com/r/BluePrince/comments/abc123/example_hint_thread/"]
    )[0]
    raw_path = fetcher.fetch(ref).raw_path
    processed_path = test_dir / "processed" / "reddit_chunks.jsonl"

    chunks = process_raw_documents_to_chunks(
        raw_paths=[raw_path],
        output_path=processed_path,
        normalizer=BluePrinceRedditNormalizer(),
        chunk_size=200,
        overlap=20,
    )

    assert chunks
    lines = [json.loads(line) for line in processed_path.read_text(encoding="utf-8").splitlines()]
    assert all(line["game_id"] == "blue_prince" for line in lines)
    assert all(line["source_id"] == "blue_prince_reddit" for line in lines)
    assert all(line["content_type"] == "community_tip" for line in lines)
    assert any(line["section"] == "Top comments" for line in lines)
    assert any("Parlor puzzle" in line["text"] for line in lines)
