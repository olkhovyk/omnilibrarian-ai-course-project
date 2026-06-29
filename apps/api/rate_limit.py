from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


logger = logging.getLogger(__name__)


@dataclass
class RateLimitExceeded(Exception):
    limit_name: str
    retry_after_seconds: int


class NullRateLimiter:
    def check(self, identifier: str) -> None:
        return None


class RedisRateLimiter:
    def __init__(self, *, redis_client, requests_per_minute: int, requests_per_day: int) -> None:
        self.redis_client = redis_client
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day

    def check(self, identifier: str) -> None:
        now = datetime.now(timezone.utc)
        minute_key = f"rate:chat:{identifier}:minute:{now:%Y%m%d%H%M}"
        day_key = f"rate:chat:{identifier}:day:{now:%Y%m%d}"

        minute_count = self._increment_window(minute_key, 60)
        day_count = self._increment_window(day_key, 86400)

        if minute_count > self.requests_per_minute:
            raise RateLimitExceeded(limit_name="minute", retry_after_seconds=60)
        if day_count > self.requests_per_day:
            raise RateLimitExceeded(limit_name="day", retry_after_seconds=86400)

    def _increment_window(self, key: str, ttl_seconds: int) -> int:
        count = int(self.redis_client.incr(key))
        if count == 1:
            self.redis_client.expire(key, ttl_seconds)
        return count


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, rate_limiter, enabled: bool) -> None:
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if self.enabled and _is_chat_request(request):
            identifier = _client_identifier(request)
            try:
                self.rate_limiter.check(identifier)
            except RateLimitExceeded as exc:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(exc.retry_after_seconds)},
                    content={
                        "error": "rate_limit_exceeded",
                        "limit": exc.limit_name,
                        "retry_after_seconds": exc.retry_after_seconds,
                    },
                )
            except Exception as exc:
                logger.warning("Rate limiter unavailable; allowing request: %s", exc)
        return await call_next(request)


def build_redis_rate_limiter(
    *,
    redis_url: str,
    requests_per_minute: int,
    requests_per_day: int,
) -> RedisRateLimiter:
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("redis package is required for RedisRateLimiter.") from exc
    return RedisRateLimiter(
        redis_client=Redis.from_url(redis_url),
        requests_per_minute=requests_per_minute,
        requests_per_day=requests_per_day,
    )


def _is_chat_request(request: Request) -> bool:
    return request.method.upper() == "POST" and request.url.path in {"/v1/chat", "/chat"}


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
