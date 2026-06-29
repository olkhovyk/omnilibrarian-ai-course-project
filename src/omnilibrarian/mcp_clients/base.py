from typing import Protocol


class MCPClient(Protocol):
    def call_tool(self, game_id: str, tool_name: str, arguments: dict) -> dict:
        ...
