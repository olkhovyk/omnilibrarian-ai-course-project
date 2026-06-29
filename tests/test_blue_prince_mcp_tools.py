from mcp_servers.blue_prince import server as blue_prince_server
from mcp_servers.blue_prince.server import build_default_blue_prince_mcp_server, create_mcp_server
from mcp_servers.blue_prince.tools import (
    get_blue_prince_entity,
    search_blue_prince_knowledge,
    search_puzzle_hint,
)


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.search_calls = []
        self.entity_calls = []

    def search(self, *, game_id: str, query: str, limit: int = 5) -> list[dict]:
        self.search_calls.append({"game_id": game_id, "query": query, "limit": limit})
        return [{"title": "Drafting Studio", "game_id": game_id}]

    def get_entity(self, *, game_id: str, name: str) -> dict | None:
        self.entity_calls.append({"game_id": game_id, "name": name})
        return {
            "game_id": game_id,
            "canonical_name": name,
            "content_type": "room",
            "source_url": f"https://example.local/blue-prince/{name}",
            "aliases": [],
        }


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


def test_search_blue_prince_knowledge_scopes_query_to_blue_prince():
    service = FakeKnowledgeService()

    result = search_blue_prince_knowledge(service=service, query="drafting studio", limit=2)

    assert result["game_id"] == "blue_prince"
    assert result["results"] == [{"title": "Drafting Studio", "game_id": "blue_prince"}]
    assert service.search_calls == [{"game_id": "blue_prince", "query": "drafting studio", "limit": 2}]


def test_get_blue_prince_entity_scopes_lookup_to_blue_prince():
    service = FakeKnowledgeService()

    result = get_blue_prince_entity(service=service, name="Drafting Studio")

    assert result["game_id"] == "blue_prince"
    assert result["entity"]["canonical_name"] == "Drafting Studio"
    assert service.entity_calls == [{"game_id": "blue_prince", "name": "Drafting Studio"}]


def test_search_puzzle_hint_uses_blue_prince_evidence_query():
    service = FakeKnowledgeService()

    result = search_puzzle_hint(service=service, topic="safe code", limit=3)

    assert result["game_id"] == "blue_prince"
    assert result["topic"] == "safe code"
    assert result["evidence_query"] == "Blue Prince puzzle hint safe code"
    assert service.search_calls == [
        {"game_id": "blue_prince", "query": "Blue Prince puzzle hint safe code", "limit": 3}
    ]


def test_create_mcp_server_registers_blue_prince_tools():
    service = FakeKnowledgeService()

    server = create_mcp_server(service=service, fast_mcp_cls=FakeFastMCP)

    assert server.name == "omnilibrarian-blue-prince"
    assert server.kwargs == {"host": "127.0.0.1", "port": 8766, "streamable_http_path": "/mcp"}
    assert set(server.tools) == {
        "search_blue_prince_knowledge",
        "get_blue_prince_entity",
        "search_puzzle_hint",
    }
    assert server.tools["search_blue_prince_knowledge"]("room", 1)["game_id"] == "blue_prince"


def test_build_default_blue_prince_mcp_server_uses_knowledge_service_factory(monkeypatch):
    service = FakeKnowledgeService()
    calls = []

    def fake_build_knowledge_service():
        calls.append("build")
        return service

    monkeypatch.setattr(blue_prince_server, "build_knowledge_service", fake_build_knowledge_service)

    server = build_default_blue_prince_mcp_server(fast_mcp_cls=FakeFastMCP)

    assert calls == ["build"]
    assert server.tools["get_blue_prince_entity"]("Drafting Studio")["entity"]["canonical_name"] == "Drafting Studio"
