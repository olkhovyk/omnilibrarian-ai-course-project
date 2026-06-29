from __future__ import annotations

from omnilibrarian.mcp_clients.streamable_http import StreamableHTTPMCPClient


class BluePrinceMCPClient(StreamableHTTPMCPClient):
    def __init__(self, *, url: str = "http://127.0.0.1:8766/mcp") -> None:
        super().__init__(game_id="blue_prince", url=url)
