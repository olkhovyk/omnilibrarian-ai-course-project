from omnilibrarian.rag.embeddings import EmbeddingProvider
from omnilibrarian.rag.query_rewriting import rewrite_query
from omnilibrarian.rag.reranking import rerank_results


class Retriever:
    def __init__(self, *, embedding_provider: EmbeddingProvider, vector_store, entity_registry=None) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.entity_registry = entity_registry

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
        candidates = self.vector_store.search(
            query_vector=query_vector,
            game_id=game_id,
            limit=candidate_limit,
        )
        results = rerank_results(rewritten_query.retrieval_query, candidates, limit=limit)
        return [
            {
                **result,
                "original_query": rewritten_query.original_query,
                "retrieval_query": rewritten_query.retrieval_query,
                "rewrite_reasons": rewritten_query.rewrite_reasons,
            }
            for result in results
        ]
