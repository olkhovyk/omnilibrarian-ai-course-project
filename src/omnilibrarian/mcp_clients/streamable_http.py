from __future__ import annotations

import json
from typing import Any

import anyio


class StreamableHTTPMCPClient:
    def __init__(self, *, game_id: str, url: str) -> None:
        self.game_id = game_id
        self.url = url

    def call_tool(self, game_id: str, tool_name: str, arguments: dict) -> dict:
        if game_id != self.game_id:
            raise ValueError(f"{type(self).__name__} cannot serve game_id={game_id!r}")

        async def runner():
            return await self._call_tool_async(tool_name=tool_name, arguments=arguments)

        return anyio.run(runner)

    async def _call_tool_async(self, *, tool_name: str, arguments: dict) -> dict:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with streamable_http_client(self.url) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _decode_tool_result(result)


def _decode_tool_result(result: Any) -> dict:
    if getattr(result, "isError", False):
        raise RuntimeError(f"MCP tool call failed: {result}")

    content = getattr(result, "content", None) or []
    if not content:
        return {}

    first = content[0]
    text = getattr(first, "text", None)
    if text is None:
        return {"content": [str(item) for item in content]}

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    if isinstance(decoded, dict):
        return decoded
    return {"value": decoded}
