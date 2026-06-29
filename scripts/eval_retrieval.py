import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.evals.retrieval import load_retrieval_golden, run_retrieval_eval, write_eval_report
from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import load_chunk_documents
from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.qdrant_store import QdrantStore
from omnilibrarian.rag.retriever import Retriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality against a golden set.")
    parser.add_argument("--golden", default="data/evals/bg3_retrieval_golden_v1.jsonl")
    parser.add_argument("--game-id", default=None, help="Optional game id override for every golden case.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="omnilibrarian_chunks")
    parser.add_argument("--entities-path", default=None, help="Optional entity registry JSON path.")
    parser.add_argument("--hybrid-retrieval", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bm25-chunks-path", default="data/processed/bg3/bg3_wiki_seed107_chunks.jsonl")
    parser.add_argument("--bm25-extra-chunks-path", action="append", default=[])
    parser.add_argument("--model", default="BAAI/bge-m3")
    parser.add_argument("--device", default=None)
    parser.add_argument("--output", default="data/evals/bg3_retrieval_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_retrieval_golden(args.golden)
    if args.game_id:
        cases = [
            type(case)(
                id=case.id,
                query=case.query,
                game_id=args.game_id,
                expected_titles=case.expected_titles,
                category=case.category,
                expected_terms=case.expected_terms,
            )
            for case in cases
        ]

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
    bm25_documents = _load_bm25_documents(args.bm25_chunks_path, args.bm25_extra_chunks_path)
    if args.hybrid_retrieval and bm25_documents:
        retriever = HybridRetriever(
            embedding_provider=embedding_provider,
            vector_store=store,
            lexical_retriever=BM25Retriever.from_documents(bm25_documents),
            entity_registry=entity_registry,
        )

    evaluated_cases, metrics = run_retrieval_eval(retriever=retriever, cases=cases, limit=args.limit)
    write_eval_report(args.output, cases=evaluated_cases, metrics=metrics)

    print("Retrieval eval")
    print(f"golden: {args.golden}")
    print(f"output: {args.output}")
    for name, value in metrics.items():
        if name == "total":
            print(f"{name}: {int(value)}")
        else:
            print(f"{name}: {value:.3f}")

    print("\nCases")
    for case in evaluated_cases:
        expected = ", ".join(case["expected_titles"])
        top_titles = ", ".join(str(title) for title in case["top_titles"])
        print(f"- {case['id']}: expected=[{expected}] top=[{top_titles}]")


def _load_bm25_documents(primary_path: str, extra_paths: list[str]) -> list:
    documents = []
    for chunks_path in [primary_path, *extra_paths]:
        path = Path(chunks_path)
        if path.exists():
            documents.extend(load_chunk_documents(path))
    return documents


if __name__ == "__main__":
    main()
