import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.entities.extract import build_entities_from_chunks
from omnilibrarian.entities.models import write_entities
from omnilibrarian.rag.documents import load_chunk_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an entity registry from processed chunks.")
    parser.add_argument("--input", required=True, help="Path to processed chunks JSONL.")
    parser.add_argument("--output", required=True, help="Path to write entity registry JSON.")
    parser.add_argument("--game-id", default=None, help="Optional game_id filter.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_chunk_documents(args.input)
    if args.game_id:
        chunks = [chunk for chunk in chunks if chunk.game_id == args.game_id]
    entities = build_entities_from_chunks(chunks)
    write_entities(args.output, entities)
    print(f"wrote {len(entities)} entity/entities -> {args.output}")


if __name__ == "__main__":
    main()
