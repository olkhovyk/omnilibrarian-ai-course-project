import pytest

from omnilibrarian.mcp_clients.registry import MCPClientRegistry


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def call_tool(self, game_id: str, tool_name: str, arguments: dict) -> dict:
        self.calls.append({"game_id": game_id, "tool_name": tool_name, "arguments": arguments})
        return {"game_id": game_id, "tool": tool_name}


def test_mcp_client_registry_dispatches_by_game_id():
    registry = MCPClientRegistry()
    bg3_client = FakeClient()
    blue_prince_client = FakeClient()
    registry.register("bg3", bg3_client)
    registry.register("blue_prince", blue_prince_client)

    result = registry.call_tool(
        game_id="blue_prince",
        tool_name="search_puzzle_hint",
        arguments={"topic": "Room 46"},
    )

    assert result == {"game_id": "blue_prince", "tool": "search_puzzle_hint"}
    assert bg3_client.calls == []
    assert blue_prince_client.calls == [
        {
            "game_id": "blue_prince",
            "tool_name": "search_puzzle_hint",
            "arguments": {"topic": "Room 46"},
        }
    ]


def test_mcp_client_registry_raises_clear_error_for_unknown_game():
    registry = MCPClientRegistry()
    registry.register("bg3", FakeClient())

    with pytest.raises(KeyError, match="No MCP client registered"):
        registry.call_tool(game_id="blue_prince", tool_name="search_puzzle_hint", arguments={})
