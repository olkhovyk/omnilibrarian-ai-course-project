from __future__ import annotations

from uuid import uuid5, NAMESPACE_URL

from omnilibrarian.rag.documents import ChunkDocument


def build_qdrant_payloads(documents: list[ChunkDocument]) -> list[dict]:
    return [
        {
            "chunk_id": document.chunk_id,
            "game_id": document.game_id,
            "source_id": document.source_id,
            "source_url": document.source_url,
            "title": document.title,
            "content_type": document.content_type,
            "language": document.language,
            "section": document.section,
            "spoiler_level": document.spoiler_level,
            "text": document.text,
        }
        for document in documents
    ]


def stable_point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, chunk_id))


class QdrantStore:
    def __init__(
        self,
        *,
        url: str = "http://localhost:6333",
        collection_name: str = "omnilibrarian_chunks",
        vector_size: int = 1024,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError(
                "qdrant-client is required for vector indexing. "
                "Install it with: python -m pip install qdrant-client"
            ) from exc

        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client = QdrantClient(url=url)

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        collections = self.client.get_collections().collections
        if any(collection.name == self.collection_name for collection in collections):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )

    def upsert_documents(
        self,
        *,
        documents: list[ChunkDocument],
        vectors: list[list[float]],
        batch_size: int = 64,
    ) -> None:
        if len(documents) != len(vectors):
            raise ValueError("documents and vectors must have the same length")

        from qdrant_client.models import PointStruct

        payloads = build_qdrant_payloads(documents)
        points = [
            PointStruct(
                id=stable_point_id(document.chunk_id),
                vector=vector,
                payload=payload,
            )
            for document, vector, payload in zip(documents, vectors, payloads, strict=True)
        ]
        for start in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start : start + batch_size],
            )

    def delete_game_documents(self, *, game_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="game_id",
                            match=MatchValue(value=game_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def delete_source_documents(self, *, game_id: str, source_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="game_id",
                            match=MatchValue(value=game_id),
                        ),
                        FieldCondition(
                            key="source_id",
                            match=MatchValue(value=source_id),
                        ),
                    ]
                )
            ),
            wait=True,
        )

    def search(self, query_vector: list[float], game_id: str, limit: int) -> list[dict]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="game_id",
                    match=MatchValue(value=game_id),
                )
            ]
        )
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            results = response.points
        else:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        return [
            {
                **dict(result.payload or {}),
                "score": result.score,
            }
            for result in results
        ]
