from dataclasses import dataclass


@dataclass(frozen=True)
class TenantConfig:
    game_id: str
    display_name: str
    description: str
    mcp_server: str
