from __future__ import annotations

from omnilibrarian.rag.embeddings import EmbeddingProvider
from omnilibrarian.rag.query_rewriting import rewrite_query
from omnilibrarian.rag.reranking import rerank_results
from omnilibrarian.rag.source_policy import SourceRetrievalPolicy


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store,
        lexical_retriever,
        entity_registry=None,
        source_policy: SourceRetrievalPolicy | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.lexical_retriever = lexical_retriever
        self.entity_registry = entity_registry
        self.source_policy = source_policy or SourceRetrievalPolicy()

    def search(
        self,
        query: str,
        game_id: str,
        limit: int = 5,
        candidate_limit: int | None = None,
    ) -> list[dict]:
        candidate_limit = candidate_limit or max(limit * 10, 50)
        rewritten_query = rewrite_query(query, entity_registry=self.entity_registry)

        query_vector = self.embedding_provider.embed_texts([rewritten_query.retrieval_query])[0]
        vector_results = [
            {
                **result,
                "retrieval_source": "vector",
                "retrieval_sources": ["vector"],
            }
            for result in self.vector_store.search(
                query_vector=query_vector,
                game_id=game_id,
                limit=candidate_limit,
            )
        ]
        lexical_results = self.lexical_retriever.search(
            rewritten_query.retrieval_query,
            game_id=game_id,
            limit=candidate_limit,
        )

        merged = _merge_results(vector_results + lexical_results)
        merged = self.source_policy.apply(rewritten_query.retrieval_query, merged)
        results = rerank_results(rewritten_query.retrieval_query, merged, limit=limit)
        results = self.source_policy.finalize(rewritten_query.retrieval_query, results)
        return [
            {
                **result,
                "original_query": rewritten_query.original_query,
                "retrieval_query": rewritten_query.retrieval_query,
                "rewrite_reasons": rewritten_query.rewrite_reasons,
            }
            for result in results
        ]


def _merge_results(results: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for result in results:
        key = _result_key(result)
        if key not in merged:
            merged[key] = dict(result)
            order.append(key)
            continue

        existing = merged[key]
        existing["score"] = max(float(existing.get("score") or 0.0), float(result.get("score") or 0.0))
        if result.get("bm25_score") is not None:
            existing["bm25_score"] = result["bm25_score"]
        sources = list(existing.get("retrieval_sources") or [])
        for source in result.get("retrieval_sources") or [result.get("retrieval_source")]:
            if source and source not in sources:
                sources.append(source)
        existing["retrieval_sources"] = sources
        existing["retrieval_source"] = "+".join(sources)

    return [merged[key] for key in order]


def _result_key(result: dict) -> str:
    if result.get("chunk_id"):
        return str(result["chunk_id"])
    return "|".join(
        [
            str(result.get("source_url") or ""),
            str(result.get("title") or ""),
            str(result.get("section") or ""),
            str(result.get("text") or ""),
        ]
    )
