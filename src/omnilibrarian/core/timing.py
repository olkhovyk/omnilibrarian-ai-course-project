from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


@contextmanager
def elapsed_ms() -> Iterator[dict[str, int]]:
    result = {"elapsed_ms": 0}
    start = perf_counter()
    try:
        yield result
    finally:
        result["elapsed_ms"] = int((perf_counter() - start) * 1000)
