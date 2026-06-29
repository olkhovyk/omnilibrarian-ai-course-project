from omnilibrarian.mcp_clients.bg3_client import BG3MCPClient


def test_bg3_mcp_client_calls_streamable_http_tool(monkeypatch):
    calls = []

    async def fake_call(self, *, tool_name: str, arguments: dict):
        calls.append({"url": self.url, "tool_name": tool_name, "arguments": arguments})
        return {"ok": True}

    monkeypatch.setattr(BG3MCPClient, "_call_tool_async", fake_call)
    client = BG3MCPClient(url="http://127.0.0.1:8765/mcp")

    result = client.call_tool(
        game_id="bg3",
        tool_name="compare_bg3_spells",
        arguments={"spell_a": "Fireball", "spell_b": "Lightning Bolt"},
    )

    assert result == {"ok": True}
    assert calls == [
        {
            "url": "http://127.0.0.1:8765/mcp",
            "tool_name": "compare_bg3_spells",
            "arguments": {"spell_a": "Fireball", "spell_b": "Lightning Bolt"},
        }
    ]
