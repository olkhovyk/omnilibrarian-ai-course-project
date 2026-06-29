from mcp_servers.bg3.tools import compare_bg3_spells, get_bg3_entity, list_bg3_companions, search_bg3_knowledge
from mcp_servers.bg3 import server as bg3_server
from mcp_servers.bg3.server import build_default_bg3_mcp_server, create_mcp_server


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.search_calls = []
        self.entity_calls = []

    def search(self, *, game_id: str, query: str, limit: int = 5) -> list[dict]:
        self.search_calls.append({"game_id": game_id, "query": query, "limit": limit})
        return [{"title": "Fireball", "game_id": game_id}]

    def get_entity(self, *, game_id: str, name: str) -> dict | None:
        self.entity_calls.append({"game_id": game_id, "name": name})
        return {
            "game_id": game_id,
            "canonical_name": name,
            "content_type": "spell",
            "source_url": f"https://bg3.wiki/wiki/{name}",
            "aliases": [],
        }

    def list_entities(self, *, game_id: str, content_type: str | None = None, limit: int | None = None) -> list[dict]:
        return [
            {
                "game_id": game_id,
                "canonical_name": "Astarion",
                "normalized_name": "astarion",
                "content_type": content_type or "character",
                "source_url": "https://bg3.wiki/wiki/Astarion",
                "aliases": [],
            }
        ][:limit]


def test_search_bg3_knowledge_scopes_query_to_bg3():
    service = FakeKnowledgeService()

    result = search_bg3_knowledge(service=service, query="Fireball damage", limit=2)

    assert result["game_id"] == "bg3"
    assert result["results"] == [{"title": "Fireball", "game_id": "bg3"}]
    assert service.search_calls == [{"game_id": "bg3", "query": "Fireball damage", "limit": 2}]


def test_get_bg3_entity_scopes_lookup_to_bg3():
    service = FakeKnowledgeService()

    result = get_bg3_entity(service=service, name="Astarion")

    assert result["game_id"] == "bg3"
    assert result["entity"]["canonical_name"] == "Astarion"
    assert service.entity_calls == [{"game_id": "bg3", "name": "Astarion"}]


def test_compare_bg3_spells_returns_entities_and_evidence():
    service = FakeKnowledgeService()

    result = compare_bg3_spells(service=service, spell_a="Fireball", spell_b="Lightning Bolt", limit=4)

    assert result["game_id"] == "bg3"
    assert result["spell_a"]["canonical_name"] == "Fireball"
    assert result["spell_b"]["canonical_name"] == "Lightning Bolt"
    assert result["evidence"] == [{"title": "Fireball", "game_id": "bg3"}]
    assert service.search_calls == [
        {
            "game_id": "bg3",
            "query": "Compare Fireball and Lightning Bolt damage range saves scaling",
            "limit": 4,
        }
    ]


def test_list_bg3_companions_returns_structured_entities_and_evidence():
    service = FakeKnowledgeService()

    result = list_bg3_companions(service=service, limit=10)

    assert result["game_id"] == "bg3"
    assert result["content_type"] == "character"
    assert result["companions"][0]["canonical_name"] == "Astarion"
    assert result["evidence"][0]["title"] == "Astarion"
    assert result["evidence"][0]["source_url"] == "https://bg3.wiki/wiki/Astarion"


class FakeFastMCP:
    def __init__(self, name: str, **kwargs) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools = {}

    def tool(self, name: str | None = None, **kwargs):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


def test_create_mcp_server_registers_bg3_tools():
    service = FakeKnowledgeService()

    server = create_mcp_server(service=service, fast_mcp_cls=FakeFastMCP)

    assert server.name == "omnilibrarian-bg3"
    assert server.kwargs == {"host": "127.0.0.1", "port": 8765, "streamable_http_path": "/mcp"}
    assert set(server.tools) == {
        "search_bg3_knowledge",
        "get_bg3_entity",
        "list_bg3_companions",
        "compare_bg3_spells",
        "roll_dice",
    }
    assert server.tools["search_bg3_knowledge"]("Fireball", 1)["game_id"] == "bg3"


def test_build_default_bg3_mcp_server_uses_knowledge_service_factory(monkeypatch):
    service = FakeKnowledgeService()
    calls = []

    def fake_build_knowledge_service():
        calls.append("build")
        return service

    monkeypatch.setattr(bg3_server, "build_knowledge_service", fake_build_knowledge_service)

    server = build_default_bg3_mcp_server(fast_mcp_cls=FakeFastMCP)

    assert calls == ["build"]
    assert server.tools["get_bg3_entity"]("Astarion")["entity"]["canonical_name"] == "Astarion"
