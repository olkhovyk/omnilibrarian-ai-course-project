import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
DOTENV_PATH = PROJECT_ROOT / ".env"

from dotenv import load_dotenv

load_dotenv(DOTENV_PATH)

from omnilibrarian.answering import AnswerGenerator
from omnilibrarian.cache.llm_cache import NullLLMCache, build_redis_llm_cache
from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.evals.answer import load_answer_golden, run_answer_eval, write_answer_eval_report
from omnilibrarian.llm.openai_provider import OpenAIProvider
from omnilibrarian.llm.openrouter_provider import OpenRouterProvider
from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import load_chunk_documents
from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.qdrant_store import QdrantStore
from omnilibrarian.rag.retriever import Retriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated answers against a golden set.")
    parser.add_argument("--golden", default="data/evals/blue_prince_answer_golden_v1.jsonl")
    parser.add_argument("--game-id", default=None, help="Optional game id override for every golden case.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "omnilibrarian_chunks"))
    parser.add_argument("--entities-path", default=None)
    parser.add_argument("--hybrid-retrieval", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bm25-chunks-path", default=os.getenv("BM25_CHUNKS_PATH", "data/processed/bg3/bg3_wiki_seed107_chunks.jsonl"))
    parser.add_argument(
        "--bm25-extra-chunks-path",
        action="append",
        default=_env_list("BM25_EXTRA_CHUNKS_PATHS"),
    )
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--device", default=os.getenv("EMBEDDING_DEVICE", None))
    parser.add_argument("--llm-provider", choices=["openai", "openrouter"], default=os.getenv("LLM_PROVIDER", "openrouter"))
    parser.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "openai/gpt-4.1-mini"))
    parser.add_argument("--llm-cache", action=argparse.BooleanOptionalAction, default=os.getenv("LLM_CACHE_ENABLED", "true").casefold() == "true")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    parser.add_argument("--llm-cache-ttl-seconds", type=int, default=int(os.getenv("LLM_CACHE_TTL_SECONDS", "86400")))
    parser.add_argument("--output", default="data/evals/blue_prince_answer_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_answer_golden(args.golden)
    if args.game_id:
        cases = [
            type(case)(
                id=case.id,
                query=case.query,
                game_id=args.game_id,
                expected_source_titles=case.expected_source_titles,
                expected_answer_terms=case.expected_answer_terms,
                category=case.category,
                allow_insufficient_context=case.allow_insufficient_context,
            )
            for case in cases
        ]

    embedding_provider = SentenceTransformerEmbeddingProvider(model_name=args.embedding_model, device=args.device)
    store = QdrantStore(url=args.qdrant_url, collection_name=args.collection, vector_size=1)
    entity_registry = EntityRegistry(load_entities(args.entities_path)) if args.entities_path else None
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

    answer_generator = AnswerGenerator(
        llm_provider=_build_llm_provider(args),
        llm_cache=_build_llm_cache(args),
        provider_name=args.llm_provider,
        model_name=args.llm_model,
    )
    evaluated_cases, metrics = run_answer_eval(
        retriever=retriever,
        answer_generator=answer_generator,
        cases=cases,
        limit=args.limit,
    )
    write_answer_eval_report(args.output, cases=evaluated_cases, metrics=metrics)

    print("Answer eval")
    print(f"golden: {args.golden}")
    print(f"output: {args.output}")
    for name, value in metrics.items():
        if name.endswith(".total") or name == "total":
            print(f"{name}: {int(value)}")
        else:
            print(f"{name}: {value:.3f}")

    print("\nCases")
    for case in evaluated_cases:
        print(
            f"- {case['id']}: source_hit={case['source_hit']} "
            f"citations={case['citation_present']} "
            f"term_coverage={case['answer_term_coverage']:.3f} "
            f"cache={case['cache_status']}"
        )


def _build_llm_provider(args: argparse.Namespace):
    if args.llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY is required when --llm-provider openai.")
        return OpenAIProvider(api_key=api_key, model=args.llm_model)

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required when --llm-provider openrouter.")
    return OpenRouterProvider(api_key=api_key, model=args.llm_model)


def _build_llm_cache(args: argparse.Namespace):
    if not args.llm_cache:
        return NullLLMCache()
    try:
        return build_redis_llm_cache(redis_url=args.redis_url, ttl_seconds=args.llm_cache_ttl_seconds)
    except Exception as exc:
        print(f"Warning: Redis LLM cache unavailable, using no-op cache: {exc}")
        return NullLLMCache()


def _load_bm25_documents(primary_path: str, extra_paths: list[str]) -> list:
    documents = []
    for chunks_path in [primary_path, *extra_paths]:
        path = Path(chunks_path)
        if path.exists():
            documents.extend(load_chunk_documents(path))
    return documents


def _env_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    if not value:
        return []
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


if __name__ == "__main__":
    main()
