import argparse
from pathlib import Path
import sys

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.ingestion.cache import IngestionCache
from omnilibrarian.ingestion.normalize import process_raw_documents_to_chunks
from omnilibrarian.ingestion.sources.bg3_wiki import (
    BG3_WIKI_CONTENT_TYPES,
    BG3_WIKI_SEED_PAGES,
    BG3WikiFetcher,
    build_bg3_wiki_seed_manifest,
)
from omnilibrarian.ingestion.sources.bg3_wiki_normalizer import BG3WikiNormalizer
from omnilibrarian.ingestion.sources.blue_prince_wiki import (
    BLUE_PRINCE_WIKI_CONTENT_TYPES,
    BLUE_PRINCE_WIKI_SEED_PAGES,
    BluePrinceWikiFetcher,
    build_blue_prince_wiki_seed_manifest,
)
from omnilibrarian.ingestion.sources.blue_prince_wiki_normalizer import BluePrinceWikiNormalizer
from omnilibrarian.ingestion.sources.blue_prince_reddit import (
    BluePrinceRedditFetcher,
    build_blue_prince_reddit_manifest,
)
from omnilibrarian.ingestion.sources.blue_prince_reddit_normalizer import BluePrinceRedditNormalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and cache source documents for OmniLibrarian.")
    parser.add_argument("--game-id", default="bg3", choices=["bg3", "blue_prince"])
    parser.add_argument("--source", default="bg3_wiki", choices=["bg3_wiki", "blue_prince_wiki", "blue_prince_reddit"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--manifest-mode", choices=["seed", "category", "all"], default="seed")
    parser.add_argument("--category-limit", type=int, default=100)
    parser.add_argument(
        "--category",
        action="append",
        help="Fetch only a specific source category. Can be passed multiple times.",
    )
    parser.add_argument(
        "--reddit-url",
        action="append",
        help="Curated r/BluePrince Reddit permalink. Can be passed multiple times.",
    )
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--ttl-hours", type=int, default=168)
    parser.add_argument("--request-delay-seconds", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=10.0)
    parser.add_argument("--cache-db", default="data/cache/ingestion.sqlite")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--processed-path", default=None)
    parser.add_argument("--process", action="store_true", help="Normalize fetched raw documents and write chunks.")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cache = IngestionCache(args.cache_db)
    fetcher, refs, normalizer, processed_path = _build_ingestion_plan(args=args, cache=cache)
    if args.limit is not None:
        refs = refs[: args.limit]

    print(f"Fetching {len(refs)} {args.source} document(s) for {args.game_id}.")
    raw_paths = []
    skipped = 0
    for ref in refs:
        try:
            result = fetcher.fetch(ref, ttl_hours=args.ttl_hours, force_refresh=args.force_refresh)
        except httpx.HTTPStatusError as exc:
            if args.source != "blue_prince_reddit" or exc.response.status_code not in {403, 429, 500, 502, 503, 504}:
                raise
            skipped += 1
            print(
                "skipped: "
                f"{ref.doc_id} -> HTTP {exc.response.status_code}. "
                "Reddit blocked the request and no cached raw document was available."
            )
            continue
        raw_paths.append(result.raw_path)
        print(f"{result.status}: {ref.doc_id} -> {result.raw_path}")

    if args.process:
        if not raw_paths and args.source == "blue_prince_reddit" and Path(processed_path).exists():
            print(
                "processed: skipped. "
                f"All {skipped} Reddit fetch(es) failed, preserving existing chunks at {processed_path}."
            )
            return
        chunks = process_raw_documents_to_chunks(
            raw_paths=raw_paths,
            output_path=processed_path,
            normalizer=normalizer,
            chunk_size=args.chunk_size,
            overlap=args.chunk_overlap,
        )
        print(f"processed: {len(chunks)} chunk(s) -> {processed_path}")


def _build_ingestion_plan(*, args: argparse.Namespace, cache: IngestionCache):
    if args.source == "bg3_wiki":
        _validate_source_game(args=args, expected_game_id="bg3")
        fetcher = BG3WikiFetcher(cache=cache, raw_root=Path(args.raw_root))
        refs = _build_bg3_refs(args=args, fetcher=fetcher)
        processed_path = args.processed_path or "data/processed/bg3/bg3_wiki_chunks.jsonl"
        return fetcher, refs, BG3WikiNormalizer(), processed_path

    if args.source == "blue_prince_wiki":
        _validate_source_game(args=args, expected_game_id="blue_prince")
        fetcher = BluePrinceWikiFetcher(
            cache=cache,
            raw_root=Path(args.raw_root),
            request_delay_seconds=args.request_delay_seconds
            if args.request_delay_seconds is not None
            else 1.0,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
        )
        refs = _build_blue_prince_refs(args=args, fetcher=fetcher)
        processed_path = args.processed_path or "data/processed/blue_prince/blue_prince_wiki_chunks.jsonl"
        return fetcher, refs, BluePrinceWikiNormalizer(), processed_path

    if args.source == "blue_prince_reddit":
        _validate_source_game(args=args, expected_game_id="blue_prince")
        fetcher = BluePrinceRedditFetcher(
            cache=cache,
            raw_root=Path(args.raw_root),
            request_delay_seconds=args.request_delay_seconds
            if args.request_delay_seconds is not None
            else 1.0,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
        )
        refs = build_blue_prince_reddit_manifest(args.reddit_url)
        if args.max_documents is not None:
            refs = refs[: args.max_documents]
        processed_path = args.processed_path or "data/processed/blue_prince/blue_prince_reddit_chunks.jsonl"
        return fetcher, refs, BluePrinceRedditNormalizer(), processed_path

    raise SystemExit(f"Unsupported source: {args.source}")


def _validate_source_game(*, args: argparse.Namespace, expected_game_id: str) -> None:
    if args.game_id != expected_game_id:
        raise SystemExit(f"Source {args.source} requires --game-id {expected_game_id}.")


def _build_bg3_refs(*, args: argparse.Namespace, fetcher: BG3WikiFetcher):
    if args.category:
        _validate_categories(args.category, allowed=BG3_WIKI_CONTENT_TYPES, source=args.source)
    if args.manifest_mode == "all":
        raise SystemExit("BG3 does not support --manifest-mode all. Use --manifest-mode category.")
    if args.manifest_mode == "category":
        return fetcher.discover_manifest(
            categories=args.category,
            per_category_limit=args.category_limit,
            max_documents=args.max_documents,
        )

    unsupported_seed_categories = sorted(set(args.category or []) - set(BG3_WIKI_SEED_PAGES))
    if unsupported_seed_categories:
        raise SystemExit(
            "Seed manifest does not include these categories: "
            f"{', '.join(unsupported_seed_categories)}. "
            "Use --manifest-mode category for discovered BG3 wiki categories."
        )
    return build_bg3_wiki_seed_manifest(
        categories=args.category,
        max_documents=args.max_documents,
    )


def _build_blue_prince_refs(*, args: argparse.Namespace, fetcher: BluePrinceWikiFetcher):
    if args.category:
        _validate_categories(args.category, allowed=BLUE_PRINCE_WIKI_CONTENT_TYPES, source=args.source)
    if args.manifest_mode == "category":
        raise SystemExit("Blue Prince wiki uses --manifest-mode all or --manifest-mode seed.")
    if args.manifest_mode == "all":
        return fetcher.discover_all_pages_manifest(max_documents=args.max_documents)

    unsupported_seed_categories = sorted(set(args.category or []) - set(BLUE_PRINCE_WIKI_SEED_PAGES))
    if unsupported_seed_categories:
        raise SystemExit(
            "Seed manifest does not include these categories: "
            f"{', '.join(unsupported_seed_categories)}. "
            "Use --manifest-mode all for discovered Blue Prince wiki pages."
        )
    return build_blue_prince_wiki_seed_manifest(
        categories=args.category,
        max_documents=args.max_documents,
    )


def _validate_categories(categories: list[str], *, allowed, source: str) -> None:
    unknown = sorted(set(categories) - set(allowed))
    if unknown:
        raise SystemExit(f"Unknown categories for {source}: {', '.join(unknown)}")


if __name__ == "__main__":
    main()
