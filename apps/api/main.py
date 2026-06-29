from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from apps.api.routes import chat, health
from apps.api.rate_limit import NullRateLimiter, RateLimitMiddleware, build_redis_rate_limiter
from pathlib import Path
from omnilibrarian.core.config import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def create_app(
    chat_service=None,
    warmup_on_startup: bool | None = None,
    rate_limiter=None,
    rate_limit_enabled: bool | None = None,
) -> FastAPI:
    settings = load_settings()
    should_warmup = settings.warmup_on_startup if warmup_on_startup is None else warmup_on_startup
    should_rate_limit = settings.rate_limit_enabled if rate_limit_enabled is None else rate_limit_enabled

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if should_warmup:
            service = app.state.chat_service
            if service is None:
                from apps.api.services.chat_service import build_default_chat_service

                service = build_default_chat_service()
                app.state.chat_service = service
            service.warmup()
        yield

    app = FastAPI(
        title="OmniLibrarian API",
        version="0.1.0",
        description="Multi-tenant AI gateway for game knowledge bases.",
        lifespan=lifespan,
    )
    app.state.chat_service = chat_service
    app.state.rate_limiter = rate_limiter or _build_rate_limiter(settings, should_rate_limit)
    app.add_middleware(
        RateLimitMiddleware,
        rate_limiter=app.state.rate_limiter,
        enabled=should_rate_limit,
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


def _build_rate_limiter(settings, enabled: bool):
    if not enabled:
        return NullRateLimiter()
    try:
        return build_redis_rate_limiter(
            redis_url=settings.redis_url,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            requests_per_day=settings.rate_limit_requests_per_day,
        )
    except Exception:
        return NullRateLimiter()


app = create_app()
