import pytest

from apps.api.rate_limit import RateLimitExceeded, RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.expire_calls = []

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expire_calls.append({"key": key, "seconds": seconds})


def test_redis_rate_limiter_allows_requests_under_limits():
    redis = FakeRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        requests_per_minute=2,
        requests_per_day=10,
    )

    limiter.check("client-1")
    limiter.check("client-1")

    assert any(call["seconds"] == 60 for call in redis.expire_calls)
    assert any(call["seconds"] == 86400 for call in redis.expire_calls)


def test_redis_rate_limiter_rejects_when_minute_limit_exceeded():
    redis = FakeRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        requests_per_minute=1,
        requests_per_day=10,
    )

    limiter.check("client-1")
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("client-1")

    assert exc_info.value.retry_after_seconds == 60
    assert exc_info.value.limit_name == "minute"


def test_redis_rate_limiter_rejects_when_day_limit_exceeded():
    redis = FakeRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        requests_per_minute=10,
        requests_per_day=1,
    )

    limiter.check("client-1")
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("client-1")

    assert exc_info.value.retry_after_seconds == 86400
    assert exc_info.value.limit_name == "day"
