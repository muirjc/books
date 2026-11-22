"""Space requests to a source (spec 002 FR-018; research R2, R9).

One limiter per app process. With two processes and 2 s spacing, the app sends at most
about one request a second to Open Library, its limit for clients without a contact
address. A wait that would end after the member request's deadline fails at once, so the
10 s budget (FR-016) covers waiting too.

Each caller reserves its slot straight away and then sleeps without holding anything, so a
request queued behind others is refused at once when its slot would come after its
deadline, rather than waiting in line first (books-0tw.1).
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
        self._next: float | None = None  # the earliest free slot

    async def acquire(self, deadline: float) -> None:
        """Wait for this process's next slot, or raise at once if it comes after
        ``deadline``. Reserving the slot has no await in it, so concurrent callers in one
        event loop each get a distinct slot."""
        now = self._clock()
        slot = now if self._next is None else max(now, self._next)
        if slot > deadline:
            raise SourceUnavailable()
        self._next = slot + self._interval
        if slot > now:
            await self._sleep(slot - now)
