from __future__ import annotations

import json
from pathlib import Path

from omnilibrarian.tenants.models import TenantConfig


class TenantRegistry:
    def __init__(self, tenants: list[TenantConfig]) -> None:
        self._tenants = {tenant.game_id: tenant for tenant in tenants}

    def game_ids(self) -> list[str]:
        return list(self._tenants.keys())

    def get(self, game_id: str) -> TenantConfig:
        try:
            return self._tenants[game_id]
        except KeyError as exc:
            known = ", ".join(self.game_ids())
            raise KeyError(f"Unknown game_id '{game_id}'. Known tenants: {known}") from exc


def load_tenant_registry(path: str | Path) -> TenantRegistry:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    tenants = [
        TenantConfig(
            game_id=item["game_id"],
            display_name=item["display_name"],
            description=item["description"],
            mcp_server=item["mcp_server"],
        )
        for item in data["tenants"]
    ]
    return TenantRegistry(tenants)
