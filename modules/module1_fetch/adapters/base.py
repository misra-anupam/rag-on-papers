import asyncio
import time
from abc import ABC, abstractmethod

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def make_retry(max_attempts: int = 5):
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )


class RateLimiter:
    """Simple async leaky-bucket rate limiter — enforces a strict minimum interval between calls with no burst capacity."""

    def __init__(self, rate: float) -> None:
        self._min_interval = 1.0 / rate
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class BaseAdapter(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[str]:
        """Return source-native IDs matching the query."""

    @abstractmethod
    async def fetch(self, paper_id: str) -> bytes:
        """Download the raw artefact (PDF or XML bytes) for a paper ID."""

    async def resolve_doi(self, paper_id: str) -> str | None:
        """Return the DOI for a paper ID, or None if unresolvable."""
        return None
