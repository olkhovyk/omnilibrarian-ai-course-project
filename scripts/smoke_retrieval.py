import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import load_chunk_documents
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.qdrant_store import QdrantStore
from omnilibrarian.rag.retriever import Retriever
from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry


def format_result(index: int, result: dict) -> str:
    text = result.get("text", "").replace("\n", " ")
    score = float(result.get("score") or 0.0)
    rerank_score = float(result.get("rerank_score", score))
    reasons = ", ".join(result.get("rerank_reasons") or ["none"])
    lines = [
        f"#{index} score={score:.4f} rerank={rerank_score:.4f}",
        f"reasons={reasons}",
    ]
    if result.get("retrieval_query") and result.get("retrieval_query") != result.get("original_query"):
        rewrite_reasons = ", ".join(result.get("rewrite_reasons") or ["none"])
        lines.append(f"retrieval_query={result.get('retrieval_query')}")
        lines.append(f"rewrite_reasons={rewrite_reasons}")
    lines.extend(
        [
            f"title={result.get('title')} section={result.get('section')} type={result.get('content_type')}",
            f"url={result.get('source_url')}",
            text,
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a smoke retrieval query against Qdrant.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--game-id", default="bg3")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="omnilibrarian_chunks")
    parser.add_argument("--entities-path", default=None, help="Optional entity registry JSON path.")
    parser.add_argument("--hybrid-retrieval", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bm25-chunks-path", default="data/processed/bg3/bg3_wiki_seed107_chunks.jsonl")
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    embedding_provider = SentenceTransformerEmbeddingProvider(model_name=args.model, device=args.device)
    store = QdrantStore(
        url=args.qdrant_url,
        collection_name=args.collection,
        vector_size=1,
    )
    entity_registry = None
    if args.entities_path:
        entity_registry = EntityRegistry(load_entities(args.entities_path))
    retriever = Retriever(
        embedding_provider=embedding_provider,
        vector_store=store,
        entity_registry=entity_registry,
    )
    bm25_chunks_path = Path(args.bm25_chunks_path)
    if args.hybrid_retrieval and bm25_chunks_path.exists():
        retriever = HybridRetriever(
            embedding_provider=embedding_provider,
            vector_store=store,
            lexical_retriever=BM25Retriever.from_documents(load_chunk_documents(bm25_chunks_path)),
            entity_registry=entity_registry,
        )
    results = retriever.search(args.query, game_id=args.game_id, limit=args.limit)

    print(f"Query: {args.query}")
    for index, result in enumerate(results, start=1):
        print(f"\n{format_result(index, result)}")


if __name__ == "__main__":
    main()
