from omnilibrarian.mcp_clients.blue_prince_client import BluePrinceMCPClient


def test_blue_prince_mcp_client_calls_streamable_http_tool(monkeypatch):
    calls = []

    async def fake_call(self, *, tool_name: str, arguments: dict):
        calls.append({"url": self.url, "tool_name": tool_name, "arguments": arguments})
        return {"ok": True}

    monkeypatch.setattr(BluePrinceMCPClient, "_call_tool_async", fake_call)
    client = BluePrinceMCPClient(url="http://127.0.0.1:8766/mcp")

    result = client.call_tool(
        game_id="blue_prince",
        tool_name="search_puzzle_hint",
        arguments={"topic": "Room 46"},
    )

    assert result == {"ok": True}
    assert calls == [
        {
            "url": "http://127.0.0.1:8766/mcp",
            "tool_name": "search_puzzle_hint",
            "arguments": {"topic": "Room 46"},
        }
    ]
