from apps.api import readiness
from omnilibrarian.core.config import Settings


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "local",
        "qdrant_url": "http://localhost:6333",
        "qdrant_collection": "omnilibrarian_chunks",
        "llm_provider": "openrouter",
        "llm_model": "openai/gpt-4.1-mini",
        "openai_api_key": "",
        "openrouter_api_key": "key",
        "embedding_model": "BAAI/bge-m3",
        "embedding_device": "cuda",
        "entity_registry_path": "",
        "warmup_on_startup": True,
        "redis_url": "redis://localhost:6379/0",
        "llm_cache_enabled": False,
        "llm_cache_ttl_seconds": 86400,
        "rate_limit_enabled": False,
        "rate_limit_requests_per_minute": 10,
        "rate_limit_requests_per_day": 100,
        "hybrid_retrieval_enabled": False,
        "bm25_chunks_path": "",
        "bm25_extra_chunks_paths": "",
        "mcp_enabled": True,
        "bg3_mcp_url": "http://127.0.0.1:8765/mcp",
        "blue_prince_mcp_url": "http://127.0.0.1:8766/mcp",
    }
    values.update(overrides)
    return Settings(**values)


def test_build_readiness_report_is_not_ready_when_any_required_check_fails(monkeypatch):
    monkeypatch.setattr(readiness, "_check_tenants", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_qdrant", lambda _settings: {"ok": False, "error": "down"})
    monkeypatch.setattr(readiness, "_check_redis", lambda _settings: {"ok": True})
    monkeypatch.setattr(readiness, "_check_llm", lambda _settings: {"ok": True})
    monkeypatch.setattr(readiness, "_check_local_files", lambda _settings: {"ok": True})

    report = readiness.build_readiness_report(_settings())

    assert report["status"] == "not_ready"
    assert report["checks"]["qdrant"] == {"ok": False, "error": "down"}


def test_llm_check_requires_configured_provider_key():
    assert readiness._check_llm(_settings(openrouter_api_key="")) == {
        "ok": False,
        "provider": "openrouter",
        "model": "openai/gpt-4.1-mini",
        "configured": False,
    }
