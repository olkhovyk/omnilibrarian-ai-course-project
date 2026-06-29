import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DOTENV_PATH = PROJECT_ROOT / ".env"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.cache.maintenance import clear_redis_keys, llm_cache_pattern


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear OmniLibrarian cache namespaces safely.")
    parser.add_argument("--redis-url", default=None, help="Defaults to REDIS_URL from .env or redis://localhost:6379/0.")
    parser.add_argument("--scope", choices=["llm"], default="llm")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--apply", action="store_true", help="Actually delete matched keys. Without this, runs dry-run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(DOTENV_PATH)

    redis_url = args.redis_url or _redis_url_from_env()
    redis_client = _build_redis_client(redis_url)
    pattern = _pattern_for_scope(args.scope)
    result = clear_redis_keys(
        redis_client=redis_client,
        pattern=pattern,
        dry_run=not args.apply,
        batch_size=args.batch_size,
    )

    mode = "dry-run" if result.dry_run else "deleted"
    print(f"scope={args.scope}")
    print(f"redis_url={redis_url}")
    print(f"pattern={result.pattern}")
    print(f"matched={result.matched}")
    print(f"{mode}={result.deleted}")
    if result.dry_run:
        print("No keys were deleted. Re-run with --apply to delete matched keys.")


def _redis_url_from_env() -> str:
    import os

    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _build_redis_client(redis_url: str):
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("redis package is required. Install project dependencies first.") from exc
    return Redis.from_url(redis_url)


def _pattern_for_scope(scope: str) -> str:
    if scope == "llm":
        return llm_cache_pattern()
    raise ValueError(f"Unsupported cache scope: {scope}")


if __name__ == "__main__":
    main()
