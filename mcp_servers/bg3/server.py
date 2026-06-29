from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from omnilibrarian.knowledge.factory import build_knowledge_service
from mcp_servers.bg3.tools import (
    compare_bg3_spells,
    get_bg3_entity,
    list_bg3_companions,
    roll_dice,
    search_bg3_knowledge,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"


def build_default_bg3_mcp_server(*, fast_mcp_cls=None, host: str = "127.0.0.1", port: int = 8765):
    load_dotenv(DOTENV_PATH)
    service = build_knowledge_service()
    return create_mcp_server(service=service, fast_mcp_cls=fast_mcp_cls, host=host, port=port)


def create_mcp_server(*, service, fast_mcp_cls=None, host: str = "127.0.0.1", port: int = 8765):
    fast_mcp_cls = fast_mcp_cls or _load_fast_mcp()
    server = fast_mcp_cls("omnilibrarian-bg3", host=host, port=port, streamable_http_path="/mcp")

    @server.tool(name="search_bg3_knowledge")
    def search_bg3_knowledge_tool(query: str, limit: int = 5) -> dict:
        return search_bg3_knowledge(service=service, query=query, limit=limit)

    @server.tool(name="get_bg3_entity")
    def get_bg3_entity_tool(name: str) -> dict:
        return get_bg3_entity(service=service, name=name)

    @server.tool(name="list_bg3_companions")
    def list_bg3_companions_tool(limit: int = 50) -> dict:
        return list_bg3_companions(service=service, limit=limit)

    @server.tool(name="compare_bg3_spells")
    def compare_bg3_spells_tool(spell_a: str, spell_b: str, limit: int = 5) -> dict:
        return compare_bg3_spells(service=service, spell_a=spell_a, spell_b=spell_b, limit=limit)

    @server.tool(name="roll_dice")
    def roll_dice_tool(dice_formula: str) -> dict[str, str]:
        return roll_dice(dice_formula)

    return server


def _load_fast_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "mcp is required to run the BG3 MCP server. Install project dependencies first."
        ) from exc
    return FastMCP


def main() -> None:
    args = parse_args()
    server = build_default_bg3_mcp_server(host=args.host, port=args.port)
    server.run(transport="streamable-http")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BG3 MCP server over streamable HTTP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


if __name__ == "__main__":
    main()
