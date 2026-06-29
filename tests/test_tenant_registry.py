from omnilibrarian.tenants.registry import load_tenant_registry


def test_registry_loads_default_tenants():
    registry = load_tenant_registry("configs/tenants.yaml")

    assert registry.game_ids() == ["bg3", "blue_prince"]
    assert registry.get("bg3").display_name == "Baldur's Gate 3"
    assert registry.get("blue_prince").display_name == "Blue Prince"
