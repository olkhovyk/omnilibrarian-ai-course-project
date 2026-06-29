from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from omnilibrarian.knowledge.factory import build_knowledge_service
from mcp_servers.blue_prince.tools import (
    get_blue_prince_entity,
    search_blue_prince_knowledge,
    search_puzzle_hint,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"


def build_default_blue_prince_mcp_server(*, fast_mcp_cls=None, host: str = "127.0.0.1", port: int = 8766):
    load_dotenv(DOTENV_PATH)
    service = build_knowledge_service()
    return create_mcp_server(service=service, fast_mcp_cls=fast_mcp_cls, host=host, port=port)


def create_mcp_server(*, service, fast_mcp_cls=None, host: str = "127.0.0.1", port: int = 8766):
    fast_mcp_cls = fast_mcp_cls or _load_fast_mcp()
    server = fast_mcp_cls("omnilibrarian-blue-prince", host=host, port=port, streamable_http_path="/mcp")

    @server.tool(name="search_blue_prince_knowledge")
    def search_blue_prince_knowledge_tool(query: str, limit: int = 5) -> dict:
        return search_blue_prince_knowledge(service=service, query=query, limit=limit)

    @server.tool(name="get_blue_prince_entity")
    def get_blue_prince_entity_tool(name: str) -> dict:
        return get_blue_prince_entity(service=service, name=name)

    @server.tool(name="search_puzzle_hint")
    def search_puzzle_hint_tool(topic: str, limit: int = 5) -> dict:
        return search_puzzle_hint(service=service, topic=topic, limit=limit)

    return server


def _load_fast_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "mcp is required to run the Blue Prince MCP server. Install project dependencies first."
        ) from exc
    return FastMCP


def main() -> None:
    args = parse_args()
    server = build_default_blue_prince_mcp_server(host=args.host, port=args.port)
    server.run(transport="streamable-http")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Blue Prince MCP server over streamable HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    return parser.parse_args()


if __name__ == "__main__":
    main()
