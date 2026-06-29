import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.rag.documents import ChunkDocument, load_chunk_documents
from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.qdrant_store import QdrantStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index processed chunks into Qdrant.")
    parser.add_argument("--input", required=True, help="Path to processed chunks JSONL.")
    parser.add_argument("--game-id", default="bg3")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="omnilibrarian_chunks")
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--device", default=None, help="Example: cuda, cpu. Default lets sentence-transformers choose.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--source-id",
        default=None,
        help="Source id to rebuild. Defaults to the single source_id found in the input chunks.",
    )
    parser.add_argument(
        "--mode",
        choices=["rebuild-source", "append", "rebuild-game"],
        default="rebuild-source",
        help=(
            "Indexing mode. rebuild-source deletes only matching game_id + source_id; "
            "append deletes nothing; rebuild-game deletes all vectors for game_id and requires confirmation."
        ),
    )
    parser.add_argument("--confirm-delete-game", default=None)
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit successfully without deleting vectors when the input has no matching documents.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if args.allow_empty and (not input_path.exists() or input_path.stat().st_size == 0):
        print(f"No chunk documents found in {args.input}; skipping optional index step.")
        return
    documents = [document for document in load_chunk_documents(args.input) if document.game_id == args.game_id]
    if not documents:
        if args.allow_empty:
            print(f"No documents found for game_id={args.game_id}; skipping optional index step.")
            return
        raise SystemExit(f"No documents found for game_id={args.game_id}")
    source_id = resolve_source_id(documents=documents, requested_source_id=args.source_id)
    if args.source_id:
        documents = [document for document in documents if document.source_id == args.source_id]
    if args.limit is not None:
        documents = documents[: args.limit]
    if not documents:
        if args.allow_empty:
            print(
                f"No documents found for game_id={args.game_id}, "
                f"source_id={args.source_id}; skipping optional index step."
            )
            return
        raise SystemExit(f"No documents found for game_id={args.game_id}")
    validate_index_safety(
        mode=args.mode,
        game_id=args.game_id,
        source_id=source_id,
        confirm_delete_game=args.confirm_delete_game,
    )

    print(f"Loaded {len(documents)} chunk document(s) from {args.input}.")
    print(f"Index mode: {args.mode} (game_id={args.game_id}, source_id={source_id})")
    embedding_provider = SentenceTransformerEmbeddingProvider(model_name=args.model, device=args.device)
    vectors = []
    for start in range(0, len(documents), args.batch_size):
        batch = documents[start : start + args.batch_size]
        vectors.extend(embedding_provider.embed_texts([document.text for document in batch]))
        print(f"Embedded {min(start + args.batch_size, len(documents))}/{len(documents)} chunks.")

    vector_size = len(vectors[0])
    store = QdrantStore(
        url=args.qdrant_url,
        collection_name=args.collection,
        vector_size=vector_size,
    )
    store.ensure_collection()
    if args.mode == "rebuild-source":
        store.delete_source_documents(game_id=args.game_id, source_id=source_id)
    elif args.mode == "rebuild-game":
        store.delete_game_documents(game_id=args.game_id)
    store.upsert_documents(documents=documents, vectors=vectors, batch_size=args.batch_size)
    print(f"Indexed {len(documents)} chunks into {args.collection} at {args.qdrant_url}.")


def resolve_source_id(*, documents, requested_source_id: str | None) -> str:
    source_ids = sorted({document.source_id for document in documents})
    if requested_source_id:
        if requested_source_id not in source_ids:
            raise SystemExit(f"No documents found for source_id={requested_source_id}")
        return requested_source_id
    if len(source_ids) != 1:
        raise SystemExit(
            "Input contains multiple source_id values. Pass --source-id explicitly: "
            f"{', '.join(source_ids)}"
        )
    return source_ids[0]


def validate_index_safety(
    *,
    mode: str,
    game_id: str,
    source_id: str,
    confirm_delete_game: str | None,
) -> None:
    if mode == "rebuild-source" and not source_id:
        raise SystemExit("--mode rebuild-source requires --source-id or a single source_id in input chunks.")
    if mode == "rebuild-game" and confirm_delete_game != game_id:
        raise SystemExit(
            f"--mode rebuild-game deletes all vectors for game_id={game_id}. "
            f"Re-run with --confirm-delete-game {game_id}."
        )


if __name__ == "__main__":
    main()
