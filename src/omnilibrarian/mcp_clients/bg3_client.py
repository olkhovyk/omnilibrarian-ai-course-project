from __future__ import annotations

from omnilibrarian.mcp_clients.streamable_http import StreamableHTTPMCPClient


class BG3MCPClient(StreamableHTTPMCPClient):
    def __init__(self, *, url: str = "http://127.0.0.1:8765/mcp") -> None:
        super().__init__(game_id="bg3", url=url)
