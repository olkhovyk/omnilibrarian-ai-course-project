from __future__ import annotations

from pathlib import Path

from omnilibrarian.core.config import Settings, load_settings
from omnilibrarian.tenants.registry import load_tenant_registry


def build_readiness_report(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or load_settings()
    checks = {
        "tenants": _check_tenants(),
        "qdrant": _check_qdrant(settings),
        "redis": _check_redis(settings),
        "llm": _check_llm(settings),
        "local_files": _check_local_files(settings),
    }
    status = "ready" if all(_is_ok(check) for check in checks.values()) else "not_ready"
    return {"status": status, "checks": checks}


def _check_tenants() -> dict[str, object]:
    try:
        registry = load_tenant_registry("configs/tenants.yaml")
        return {"ok": True, "game_ids": registry.game_ids()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_qdrant(settings: Settings) -> dict[str, object]:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url)
        collections = client.get_collections().collections
        names = [collection.name for collection in collections]
        return {
            "ok": settings.qdrant_collection in names,
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "collections": names,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection,
            "error": str(exc),
        }


def _check_redis(settings: Settings) -> dict[str, object]:
    if not settings.llm_cache_enabled and not settings.rate_limit_enabled:
        return {"ok": True, "enabled": False}
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
        return {"ok": True, "enabled": True, "url": settings.redis_url}
    except Exception as exc:
        return {"ok": False, "enabled": True, "url": settings.redis_url, "error": str(exc)}


def _check_llm(settings: Settings) -> dict[str, object]:
    if settings.llm_provider == "openai":
        return {
            "ok": bool(settings.openai_api_key),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "configured": bool(settings.openai_api_key),
        }
    if settings.llm_provider == "openrouter":
        return {
            "ok": bool(settings.openrouter_api_key),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "configured": bool(settings.openrouter_api_key),
        }
    return {
        "ok": False,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "error": "unsupported_llm_provider",
    }


def _check_local_files(settings: Settings) -> dict[str, object]:
    files: dict[str, dict[str, object]] = {}
    if settings.entity_registry_path:
        files["entity_registry"] = _file_check(settings.entity_registry_path)
    if settings.hybrid_retrieval_enabled:
        files["bm25_chunks"] = _file_check(settings.bm25_chunks_path)
    return {"ok": all(_is_ok(check) for check in files.values()), "files": files}


def _file_check(path: str) -> dict[str, object]:
    file_path = Path(path)
    return {"ok": file_path.exists(), "path": path}


def _is_ok(check: object) -> bool:
    return isinstance(check, dict) and bool(check.get("ok"))
