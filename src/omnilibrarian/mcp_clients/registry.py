from omnilibrarian.mcp_clients.base import MCPClient


class MCPClientRegistry:
    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}

    def register(self, game_id: str, client: MCPClient) -> None:
        self._clients[game_id] = client

    def get(self, game_id: str) -> MCPClient:
        try:
            return self._clients[game_id]
        except KeyError as exc:
            known = ", ".join(sorted(self._clients))
            raise KeyError(f"No MCP client registered for game_id={game_id!r}. Known clients: {known}") from exc

    def call_tool(self, game_id: str, tool_name: str, arguments: dict) -> dict:
        return self.get(game_id).call_tool(game_id=game_id, tool_name=tool_name, arguments=arguments)
