from omnilibrarian.entities.models import Entity
from omnilibrarian.entities.registry import EntityRegistry
from omnilibrarian.knowledge.service import KnowledgeService
from omnilibrarian.tools.router import ToolRouter


class FakeRetriever:
    def search(self, query: str, game_id: str, limit: int = 5) -> list[dict]:
        return []


def _entity(name: str, content_type: str = "spell") -> Entity:
    return Entity(
        game_id="bg3",
        canonical_name=name,
        normalized_name=name.casefold(),
        content_type=content_type,
        source_url=f"https://bg3.wiki/wiki/{name.replace(' ', '_')}",
        aliases=[name.casefold()],
    )


def test_tool_router_selects_spell_comparison_from_entity_registry_not_hardcoded_names():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry(
            [
                _entity("Magic Missile"),
                _entity("Eldritch Blast"),
                _entity("Astarion", content_type="character"),
            ]
        ),
    )

    selection = ToolRouter(service).select(
        game_id="bg3",
        query="Compare Magic Missile and Eldritch Blast",
    )

    assert selection is not None
    assert selection.tool == "compare_bg3_spells"
    assert selection.arguments == {"spell_a": "Magic Missile", "spell_b": "Eldritch Blast", "limit": 5}


def test_tool_router_does_not_select_spell_tool_for_non_spell_entities():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry(
            [
                _entity("Astarion", content_type="character"),
                _entity("Shadowheart", content_type="character"),
            ]
        ),
    )

    selection = ToolRouter(service).select(
        game_id="bg3",
        query="Compare Astarion and Shadowheart",
    )

    assert selection is None


def test_tool_router_selects_companion_list_tool_from_declarative_trigger():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry([_entity("Astarion", content_type="character")]),
    )

    selection = ToolRouter(service).select(
        game_id="bg3",
        query="List all companions",
    )

    assert selection is not None
    assert selection.tool == "list_bg3_companions"
    assert selection.arguments == {"limit": 50}


def test_tool_router_selects_companion_list_tool_from_ukrainian_trigger():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry([_entity("Astarion", content_type="character")]),
    )

    selection = ToolRouter(service).select(
        game_id="bg3",
        query="Покажи всіх компаньйонів",
    )

    assert selection is not None
    assert selection.tool == "list_bg3_companions"
    assert selection.arguments == {"limit": 50}


def test_tool_router_selects_blue_prince_puzzle_hint_tool_from_declarative_trigger():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry([]),
    )

    selection = ToolRouter(service).select(
        game_id="blue_prince",
        query="I am stuck on the parlor puzzle, give me a hint",
    )

    assert selection is not None
    assert selection.tool == "search_puzzle_hint"
    assert selection.arguments == {
        "topic": "I am stuck on the parlor puzzle, give me a hint",
        "limit": 5,
    }


def test_tool_router_does_not_select_blue_prince_hint_tool_for_general_question():
    service = KnowledgeService(
        retriever=FakeRetriever(),
        entity_registry=EntityRegistry([]),
    )

    selection = ToolRouter(service).select(
        game_id="blue_prince",
        query="Who is the baron in Blue Prince?",
    )

    assert selection is None
