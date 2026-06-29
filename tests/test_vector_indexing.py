import json
from pathlib import Path
from uuid import uuid4

from omnilibrarian.rag.documents import ChunkDocument, load_chunk_documents
from omnilibrarian.rag.embeddings import DeterministicEmbeddingProvider
from omnilibrarian.rag.qdrant_store import QdrantStore, build_qdrant_payloads
from omnilibrarian.rag.retriever import Retriever
from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry


def _workspace_test_dir() -> Path:
    path = Path(".test_cache") / str(uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_load_chunk_documents_preserves_metadata():
    test_dir = _workspace_test_dir()
    chunks_path = test_dir / "chunks.jsonl"
    chunks_path.write_text(
        json.dumps(
            {
                "chunk_id": "bg3_wiki:Fireball:description:0001",
                "game_id": "bg3",
                "source_id": "bg3_wiki",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "title": "Fireball",
                "content_type": "spell",
                "language": "en",
                "section": "Lead",
                "spoiler_level": "standard",
                "text": "Fireball deals 8d6 fire damage.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    docs = load_chunk_documents(chunks_path)

    assert docs == [
        ChunkDocument(
            chunk_id="bg3_wiki:Fireball:description:0001",
            game_id="bg3",
            source_id="bg3_wiki",
            source_url="https://bg3.wiki/wiki/Fireball",
            title="Fireball",
            content_type="spell",
            language="en",
            section="Lead",
            spoiler_level="standard",
            text="Fireball deals 8d6 fire damage.",
        )
    ]


def test_deterministic_embedding_provider_returns_stable_vectors():
    provider = DeterministicEmbeddingProvider(vector_size=8)

    first = provider.embed_texts(["Fireball", "Astarion"])
    second = provider.embed_texts(["Fireball", "Astarion"])

    assert first == second
    assert len(first) == 2
    assert len(first[0]) == 8
    assert first[0] != first[1]


def test_build_qdrant_payloads_keeps_text_and_metadata():
    doc = ChunkDocument(
        chunk_id="chunk-1",
        game_id="bg3",
        source_id="bg3_wiki",
        source_url="https://bg3.wiki/wiki/Fireball",
        title="Fireball",
        content_type="spell",
        language="en",
        section="Lead",
        spoiler_level="standard",
        text="Fireball deals 8d6 fire damage.",
    )

    payload = build_qdrant_payloads([doc])[0]

    assert payload["chunk_id"] == "chunk-1"
    assert payload["game_id"] == "bg3"
    assert payload["title"] == "Fireball"
    assert payload["text"] == "Fireball deals 8d6 fire damage."


class FakeStore:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query_vector: list[float], game_id: str, limit: int) -> list[dict]:
        self.calls.append({"query_vector": query_vector, "game_id": game_id, "limit": limit})
        return [{"title": "Fireball", "score": 0.9}]


def test_retriever_embeds_query_and_searches_store_with_game_filter():
    embeddings = DeterministicEmbeddingProvider(vector_size=4)
    store = FakeStore()
    retriever = Retriever(embedding_provider=embeddings, vector_store=store)

    results = retriever.search("Fireball damage", game_id="bg3", limit=3)

    assert results[0]["title"] == "Fireball"
    assert results[0]["score"] == 0.9
    assert "rerank_score" in results[0]
    assert store.calls[0]["game_id"] == "bg3"
    assert store.calls[0]["limit"] == 50
    assert len(store.calls[0]["query_vector"]) == 4


def test_retriever_uses_explicit_candidate_limit_when_provided():
    embeddings = DeterministicEmbeddingProvider(vector_size=4)
    store = FakeStore()
    retriever = Retriever(embedding_provider=embeddings, vector_store=store)

    retriever.search("Fireball damage", game_id="bg3", limit=3, candidate_limit=9)

    assert store.calls[0]["limit"] == 9


class RecordingEmbeddingProvider:
    def __init__(self) -> None:
        self.texts = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts.append(texts)
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def test_retriever_rewrites_mixed_ukrainian_query_before_embedding():
    embeddings = RecordingEmbeddingProvider()
    store = FakeStore()
    retriever = Retriever(embedding_provider=embeddings, vector_store=store)

    results = retriever.search("Порівняй мені fireball з молнією що завдає більше шкоди", game_id="bg3")

    assert embeddings.texts[0] == ["compare fireball with Lightning Bolt damage"]
    assert results[0]["original_query"] == "Порівняй мені fireball з молнією що завдає більше шкоди"
    assert results[0]["retrieval_query"] == "compare fireball with Lightning Bolt damage"
    assert "молнією->Lightning Bolt" in results[0]["rewrite_reasons"]


def test_retriever_uses_entity_registry_for_typo_rewrite_before_embedding():
    embeddings = RecordingEmbeddingProvider()
    store = FakeStore()
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=["fireball"],
            )
        ]
    )
    retriever = Retriever(embedding_provider=embeddings, vector_store=store, entity_registry=registry)

    results = retriever.search("fireballll damage", game_id="bg3")

    assert embeddings.texts[0] == ["Fireball damage"]
    assert "fireballll->Fireball:fuzzy" in results[0]["rewrite_reasons"]


class FakeScoredPoint:
    def __init__(self, payload: dict, score: float) -> None:
        self.payload = payload
        self.score = score


class FakeQueryResponse:
    def __init__(self, points: list[FakeScoredPoint]) -> None:
        self.points = points


class FakeQdrantClientV118:
    def __init__(self) -> None:
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return FakeQueryResponse([FakeScoredPoint({"title": "Fireball", "game_id": "bg3"}, 0.95)])


def test_qdrant_store_search_uses_query_points_api_for_new_clients():
    store = QdrantStore.__new__(QdrantStore)
    store.collection_name = "omnilibrarian_chunks"
    store.client = FakeQdrantClientV118()

    results = store.search(query_vector=[0.1, 0.2], game_id="bg3", limit=5)

    assert results == [{"title": "Fireball", "game_id": "bg3", "score": 0.95}]
    call = store.client.calls[0]
    assert call["collection_name"] == "omnilibrarian_chunks"
    assert call["query"] == [0.1, 0.2]
    assert call["limit"] == 5


class FakeDeleteClient:
    def __init__(self) -> None:
        self.calls = []

    def delete(self, **kwargs):
        self.calls.append(kwargs)


def test_qdrant_store_delete_game_documents_uses_game_filter():
    store = QdrantStore.__new__(QdrantStore)
    store.collection_name = "omnilibrarian_chunks"
    store.client = FakeDeleteClient()

    store.delete_game_documents(game_id="bg3")

    call = store.client.calls[0]
    assert call["collection_name"] == "omnilibrarian_chunks"
    assert call["wait"] is True
    assert call["points_selector"].filter.must[0].key == "game_id"
    assert call["points_selector"].filter.must[0].match.value == "bg3"


def test_qdrant_store_delete_source_documents_uses_game_and_source_filter():
    store = QdrantStore.__new__(QdrantStore)
    store.collection_name = "omnilibrarian_chunks"
    store.client = FakeDeleteClient()

    store.delete_source_documents(game_id="blue_prince", source_id="blue_prince_reddit")

    call = store.client.calls[0]
    assert call["collection_name"] == "omnilibrarian_chunks"
    assert call["wait"] is True
    conditions = call["points_selector"].filter.must
    assert [(condition.key, condition.match.value) for condition in conditions] == [
        ("game_id", "blue_prince"),
        ("source_id", "blue_prince_reddit"),
    ]
