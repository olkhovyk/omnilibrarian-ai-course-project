from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.knowledge.service import KnowledgeService


class FakeRetriever:
    def __init__(self) -> None:
        self.calls = []

    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        self.calls.append({"query": query, "game_id": game_id, "limit": limit})
        return [{"title": "Fireball", "game_id": game_id}]


def test_knowledge_service_search_scopes_retrieval_by_game_id():
    retriever = FakeRetriever()
    service = KnowledgeService(retriever=retriever)

    results = service.search(game_id="bg3", query="Fireball damage", limit=3)

    assert results == [{"title": "Fireball", "game_id": "bg3"}]
    assert retriever.calls == [{"query": "Fireball damage", "game_id": "bg3", "limit": 3}]


def test_knowledge_service_get_entity_returns_only_requested_game_entity():
    registry = EntityRegistry(
        [
            Entity(
                game_id="blue_prince",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="puzzle",
                source_url="https://example.com/blue-prince/fireball",
                aliases=["Fireball"],
            ),
            Entity(
                game_id="bg3",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="spell",
                source_url="https://bg3.wiki/wiki/Fireball",
                aliases=["Fire Ball"],
            ),
        ]
    )
    service = KnowledgeService(retriever=FakeRetriever(), entity_registry=registry)

    entity = service.get_entity(game_id="bg3", name="Fire Ball")

    assert entity == {
        "game_id": "bg3",
        "canonical_name": "Fireball",
        "normalized_name": "fireball",
        "content_type": "spell",
        "source_url": "https://bg3.wiki/wiki/Fireball",
        "aliases": ["Fire Ball"],
    }


def test_knowledge_service_get_entity_returns_none_when_entity_belongs_to_other_game():
    registry = EntityRegistry(
        [
            Entity(
                game_id="blue_prince",
                canonical_name="Fireball",
                normalized_name="fireball",
                content_type="puzzle",
                source_url="https://example.com/blue-prince/fireball",
                aliases=["Fireball"],
            )
        ]
    )
    service = KnowledgeService(retriever=FakeRetriever(), entity_registry=registry)

    assert service.get_entity(game_id="bg3", name="Fireball") is None
