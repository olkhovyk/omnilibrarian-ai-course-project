import json
from pathlib import Path
from uuid import uuid4

from omnilibrarian.core.config import Settings
from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.knowledge.factory import build_knowledge_service, build_retriever
from omnilibrarian.rag.hybrid import HybridRetriever


class FakeRetriever:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        self.calls.append({"query": query, "game_id": game_id, "limit": limit})
        return [{"title": "Fireball"}]


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "local",
        "qdrant_url": "http://localhost:6333",
        "qdrant_collection": "omnilibrarian_chunks",
        "llm_provider": "openrouter",
        "llm_model": "openai/gpt-4.1-mini",
        "openai_api_key": "",
        "openrouter_api_key": "key",
        "embedding_model": "BAAI/bge-m3",
        "embedding_device": "cuda",
        "entity_registry_path": "",
        "warmup_on_startup": True,
        "redis_url": "redis://localhost:6379/0",
        "llm_cache_enabled": True,
        "llm_cache_ttl_seconds": 86400,
        "rate_limit_enabled": True,
        "rate_limit_requests_per_minute": 10,
        "rate_limit_requests_per_day": 100,
        "hybrid_retrieval_enabled": True,
        "bm25_chunks_path": "",
        "bm25_extra_chunks_paths": "",
        "mcp_enabled": True,
        "bg3_mcp_url": "http://127.0.0.1:8765/mcp",
        "blue_prince_mcp_url": "http://127.0.0.1:8766/mcp",
    }
    values.update(overrides)
    return Settings(**values)


def test_build_retriever_uses_hybrid_retrieval_when_bm25_chunks_exist():
    test_dir = Path(".test_cache") / str(uuid4())
    test_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = test_dir / "chunks.jsonl"
    chunks_path.write_text(
        json.dumps(
            {
                "chunk_id": "chunk-1",
                "game_id": "bg3",
                "source_id": "bg3_wiki",
                "source_url": "https://bg3.wiki/wiki/Fireball",
                "title": "Fireball",
                "content_type": "spell",
                "language": "en",
                "section": "Lead",
                "spoiler_level": "standard",
                "text": "Fireball deals 8d6 Fire damage.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    retriever = build_retriever(
        settings=_settings(bm25_chunks_path=str(chunks_path)),
        embedding_provider=object(),
        store=object(),
        entity_registry=None,
    )

    assert isinstance(retriever, HybridRetriever)


def test_build_retriever_loads_extra_bm25_chunks_when_configured():
    test_dir = Path(".test_cache") / str(uuid4())
    test_dir.mkdir(parents=True, exist_ok=True)
    wiki_path = test_dir / "wiki.jsonl"
    reddit_path = test_dir / "reddit.jsonl"
    wiki_path.write_text(
        json.dumps(
            {
                "chunk_id": "wiki-room",
                "game_id": "blue_prince",
                "source_id": "blue_prince_wiki",
                "source_url": "https://blueprince.wiki.gg/wiki/Room_46",
                "title": "Room 46",
                "content_type": "room",
                "language": "en",
                "section": "Lead",
                "spoiler_level": "standard",
                "text": "Room 46 is a room.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reddit_path.write_text(
        json.dumps(
            {
                "chunk_id": "reddit-room",
                "game_id": "blue_prince",
                "source_id": "blue_prince_reddit",
                "source_url": "https://reddit.test/thread",
                "title": "Room 46 hints",
                "content_type": "community_tip",
                "language": "en",
                "section": "Top comments",
                "spoiler_level": "spoiler_light",
                "text": "Community hints for Room 46.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    retriever = build_retriever(
        settings=_settings(
            bm25_chunks_path=str(wiki_path),
            bm25_extra_chunks_paths=str(reddit_path),
        ),
        embedding_provider=object(),
        store=object(),
        entity_registry=None,
    )

    source_ids = {document.source_id for document in retriever.lexical_retriever.documents}
    assert source_ids == {"blue_prince_wiki", "blue_prince_reddit"}


def test_build_knowledge_service_wraps_retriever_and_entity_registry():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=[],
            )
        ]
    )
    retriever = FakeRetriever()

    service = build_knowledge_service(
        settings=_settings(),
        retriever=retriever,
        entity_registry=registry,
    )

    assert service.search(game_id="bg3", query="Fireball damage", limit=2) == [{"title": "Fireball"}]
    assert service.get_entity(game_id="bg3", name="Fireball")["canonical_name"] == "Fireball"
    assert retriever.calls == [{"query": "Fireball damage", "game_id": "bg3", "limit": 2}]


def test_knowledge_service_lists_entities_by_game_and_content_type():
    registry = EntityRegistry(
        [
            Entity(
                game_id="bg3",
                canonical_name="Shadowheart",
                normalized_name="shadowheart",
                content_type="character",
                source_url="https://bg3.wiki/wiki/Shadowheart",
                aliases=[],
            ),
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=[],
            ),
            Entity(
                game_id="blue_prince",
                canonical_name="Room 46",
                normalized_name="room 46",
                content_type="room",
                source_url="https://example.test/room-46",
                aliases=[],
            ),
        ]
    )
    service = build_knowledge_service(
        settings=_settings(),
        retriever=FakeRetriever(),
        entity_registry=registry,
    )

    entities = service.list_entities(game_id="bg3", content_type="character")

    assert [entity["canonical_name"] for entity in entities] == ["Shadowheart"]
