"""Space requests to a source (spec 002 FR-018; research R2, R9).

One limiter per app process. With two processes and 2 s spacing, the app sends at most
about one request a second to Open Library, its limit for clients without a contact
address. A wait that would end after the member request's deadline fails at once, so the
10 s budget (FR-016) covers waiting too.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from book_tracker.services.errors import SourceUnavailable

DEFAULT_INTERVAL = 2.0


class RateLimiter:
    def __init__(
        self,
        min_interval: float = DEFAULT_INTERVAL,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def acquire(self, deadline: float) -> None:
        """Wait for this process's next slot, or raise if it comes after ``deadline``."""
        async with self._lock:
            now = self._clock()
            wait = 0.0 if self._last is None else self._last + self._interval - now
            if wait > 0:
                if now + wait > deadline:
                    raise SourceUnavailable()
                await self._sleep(wait)
            self._last = self._clock()
