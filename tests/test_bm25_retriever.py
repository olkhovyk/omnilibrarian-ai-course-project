from omnilibrarian.rag.bm25 import BM25Retriever
from omnilibrarian.rag.documents import ChunkDocument
from omnilibrarian.rag.hybrid import HybridRetriever
from omnilibrarian.rag.source_policy import SourceRetrievalPolicy


def _chunk(chunk_id: str, title: str, text: str, content_type: str = "spell") -> ChunkDocument:
    return ChunkDocument(
        chunk_id=chunk_id,
        game_id="bg3",
        source_id="bg3_wiki",
        source_url=f"https://bg3.wiki/wiki/{title.replace(' ', '_')}",
        title=title,
        content_type=content_type,
        language="en",
        section="Lead",
        spoiler_level="standard",
        text=text,
    )


def _bp_chunk(chunk_id: str, source_id: str, title: str, text: str, content_type: str = "room") -> ChunkDocument:
    return ChunkDocument(
        chunk_id=chunk_id,
        game_id="blue_prince",
        source_id=source_id,
        source_url=f"https://example.test/{chunk_id}",
        title=title,
        content_type=content_type,
        language="en",
        section="Lead",
        spoiler_level="standard",
        text=text,
    )


def test_bm25_retriever_prioritizes_exact_title_and_terms():
    retriever = BM25Retriever.from_documents(
        [
            _chunk("fireball-1", "Fireball", "Deals 8d6 Fire damage in a radius."),
            _chunk("initiative-1", "Initiative", "Fireball can start combat from stealth."),
            _chunk("astarion-1", "Astarion", "A vampire spawn companion."),
        ]
    )

    results = retriever.search("Fireball damage", game_id="bg3", limit=2)

    assert results[0]["title"] == "Fireball"
    assert results[0]["retrieval_source"] == "bm25"
    assert results[0]["score"] > results[1]["score"]


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query_vector: list[float], game_id: str, limit: int) -> list[dict]:
        self.calls.append({"query_vector": query_vector, "game_id": game_id, "limit": limit})
        return [
            {
                "chunk_id": "initiative-1",
                "game_id": "bg3",
                "title": "Initiative",
                "section": "Overview",
                "content_type": "mechanic",
                "text": "Fireball can interact with surprise rules.",
                "score": 0.88,
            },
            {
                "chunk_id": "fireball-1",
                "game_id": "bg3",
                "title": "Fireball",
                "section": "Lead",
                "content_type": "spell",
                "text": "Deals 8d6 Fire damage.",
                "score": 0.8,
            },
        ]


def test_hybrid_retriever_merges_vector_and_bm25_results_before_reranking():
    bm25 = BM25Retriever.from_documents(
        [
            _chunk("fireball-1", "Fireball", "Deals 8d6 Fire damage in a radius."),
            _chunk("scroll-fireball-1", "Scroll of Fireball", "Casts Fireball once."),
        ]
    )
    vector_store = FakeVectorStore()
    retriever = HybridRetriever(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=vector_store,
        lexical_retriever=bm25,
    )

    results = retriever.search("Fireball damage", game_id="bg3", limit=3)

    assert vector_store.calls[0]["limit"] == 50
    assert results[0]["title"] == "Fireball"
    assert [result["title"] for result in results].count("Fireball") == 1
    assert "Scroll of Fireball" in [result["title"] for result in results]
    assert "Initiative" in [result["title"] for result in results]
    assert results[0]["retrieval_sources"] == ["vector", "bm25"]
    assert results[0]["retrieval_query"] == "Fireball damage"


class BluePrinceVectorStore:
    def search(self, query_vector: list[float], game_id: str, limit: int) -> list[dict]:
        return [
            {
                "chunk_id": "reddit-room-46",
                "game_id": "blue_prince",
                "source_id": "blue_prince_reddit",
                "title": "Room 46 Thread",
                "section": "Top comments",
                "content_type": "community_tip",
                "text": "Community discussion with Room 46 theories and hints.",
                "score": 0.9,
            },
            {
                "chunk_id": "wiki-room-46",
                "game_id": "blue_prince",
                "source_id": "blue_prince_wiki",
                "title": "Room 46",
                "section": "Lead",
                "content_type": "room",
                "text": "Room 46 is a room in Blue Prince.",
                "score": 0.72,
            },
        ]


def test_hybrid_retriever_prefers_wiki_for_blue_prince_factual_questions():
    retriever = HybridRetriever(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=BluePrinceVectorStore(),
        lexical_retriever=BM25Retriever.from_documents(
            [
                _bp_chunk("wiki-room-46", "blue_prince_wiki", "Room 46", "Room 46 is a room in Blue Prince."),
                _bp_chunk(
                    "reddit-room-46",
                    "blue_prince_reddit",
                    "Room 46 Thread",
                    "Community discussion with Room 46 theories and hints.",
                    content_type="community_tip",
                ),
            ]
        ),
        source_policy=SourceRetrievalPolicy(),
    )

    results = retriever.search("What is Room 46?", game_id="blue_prince", limit=2)

    assert results[0]["source_id"] == "blue_prince_wiki"
    assert "source_policy:prefer_wiki_facts" in results[0]["source_policy_reasons"]


def test_hybrid_retriever_can_promote_reddit_for_blue_prince_hint_questions():
    retriever = HybridRetriever(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=BluePrinceVectorStore(),
        lexical_retriever=BM25Retriever.from_documents(
            [
                _bp_chunk("wiki-room-46", "blue_prince_wiki", "Room 46", "Room 46 is a room in Blue Prince."),
                _bp_chunk(
                    "reddit-room-46",
                    "blue_prince_reddit",
                    "Room 46 hints",
                    "Players share gentle Room 46 hints without full spoilers.",
                    content_type="community_tip",
                ),
            ]
        ),
        source_policy=SourceRetrievalPolicy(),
    )

    results = retriever.search("I am stuck, give me a hint for Room 46", game_id="blue_prince", limit=2)

    assert results[0]["source_id"] == "blue_prince_reddit"
    assert "source_policy:prefer_reddit_hints" in results[0]["source_policy_reasons"]
