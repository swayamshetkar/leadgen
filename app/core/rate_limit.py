import asyncio
import time
import random
from typing import Optional


class AsyncRateLimiter:
    """
    Async rate limiter with token-bucket or minimum inter-request delay
    to strictly prevent hitting rate limits or overwhelming target websites.
    """
    def __init__(self, min_delay: float = 1.0, max_delay: Optional[float] = None):
        self.min_delay = min_delay
        self.max_delay = max_delay if max_delay is not None else min_delay
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            required_delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < required_delay:
                await asyncio.sleep(required_delay - elapsed)
            self._last_call = time.monotonic()


class DomainRateLimiter:
    """
    Per-domain rate limiter to ensure we don't bombard any single domain.
    """
    def __init__(self, min_delay: float = 0.5):
        self.min_delay = min_delay
        self._limiters: dict[str, AsyncRateLimiter] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str):
        async with self._lock:
            if domain not in self._limiters:
                self._limiters[domain] = AsyncRateLimiter(min_delay=self.min_delay, max_delay=self.min_delay * 1.5)
            limiter = self._limiters[domain]
        await limiter.acquire()
