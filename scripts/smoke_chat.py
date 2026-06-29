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
from omnilibrarian.entities.models import load_entities
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.llm.openai_provider import OpenAIProvider
from omnilibrarian.llm.openrouter_provider import OpenRouterProvider
from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import load_chunk_documents
from omnilibrarian.rag.embeddings import SentenceTransformerEmbeddingProvider
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.qdrant_store import QdrantStore
from omnilibrarian.rag.retriever import Retriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an end-to-end retrieval + LLM smoke chat.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--game-id", default="bg3")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "omnilibrarian_chunks"))
    parser.add_argument("--entities-path", default=None)
    parser.add_argument("--hybrid-retrieval", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--bm25-chunks-path", default=os.getenv("BM25_CHUNKS_PATH", "data/processed/bg3/bg3_wiki_seed107_chunks.jsonl"))
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--device", default=os.getenv("EMBEDDING_DEVICE", None))
    parser.add_argument("--llm-provider", choices=["openai", "openrouter"], default=os.getenv("LLM_PROVIDER", "openrouter"))
    parser.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "openai/gpt-4.1-mini"))
    return parser.parse_args()


def build_llm_provider(args: argparse.Namespace):
    if args.llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY is required when --llm-provider openai.")
        return OpenAIProvider(api_key=api_key, model=args.llm_model)

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required when --llm-provider openrouter.")
    return OpenRouterProvider(api_key=api_key, model=args.llm_model)


def main() -> None:
    args = parse_args()
    entity_registry = None
    if args.entities_path:
        entity_registry = EntityRegistry(load_entities(args.entities_path))

    embedding_provider = SentenceTransformerEmbeddingProvider(model_name=args.embedding_model, device=args.device)
    store = QdrantStore(url=args.qdrant_url, collection_name=args.collection, vector_size=1)
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
    chunks = retriever.search(args.query, game_id=args.game_id, limit=args.limit)
    generator = AnswerGenerator(llm_provider=build_llm_provider(args))
    result = generator.generate(question=args.query, game_id=args.game_id, chunks=chunks)

    print(f"Question: {args.query}")
    if chunks:
        print(f"Retrieval query: {chunks[0].get('retrieval_query')}")
        print(f"Rewrite reasons: {', '.join(chunks[0].get('rewrite_reasons') or ['none'])}")
    print("\nAnswer:")
    print(result.answer)
    print("\nSources:")
    for source in result.sources:
        print(f"[{source['id']}] {source['title']} / {source['section']} / {source['url']}")


if __name__ == "__main__":
    main()
