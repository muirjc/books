"""Spacing Open Library requests (FR-016, FR-018; research R2, R9; task T009)."""

from __future__ import annotations

import pytest

from book_tracker.services.errors import SourceUnavailable
from book_tracker.sources.rate_limit import RateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _limiter(time: FakeTime) -> RateLimiter:
    return RateLimiter(min_interval=2.0, clock=time.clock, sleep=time.sleep)


async def test_first_call_does_not_wait() -> None:
    time = FakeTime()
    await _limiter(time).acquire(deadline=time.now + 10)
    assert time.slept == []


async def test_calls_close_together_are_spaced() -> None:
    time = FakeTime()
    limiter = _limiter(time)
    await limiter.acquire(deadline=time.now + 10)
    time.now += 0.5
    await limiter.acquire(deadline=time.now + 10)
    assert time.slept == [pytest.approx(1.5)]


async def test_calls_far_apart_do_not_wait() -> None:
    time = FakeTime()
    limiter = _limiter(time)
    await limiter.acquire(deadline=time.now + 10)
    time.now += 2.5
    await limiter.acquire(deadline=time.now + 10)
    assert time.slept == []


async def test_a_wait_past_the_deadline_fails_at_once() -> None:
    time = FakeTime()
    limiter = _limiter(time)
    await limiter.acquire(deadline=time.now + 10)
    time.now += 0.5
    with pytest.raises(SourceUnavailable):
        await limiter.acquire(deadline=time.now + 1.0)  # would need to wait 1.5 s
    assert time.slept == []


async def test_a_queued_request_is_refused_by_its_own_deadline() -> None:
    """books-0tw.1: while B is still waiting for its slot, C (whose slot would come after
    its deadline) is refused at once instead of queueing behind B past its 10 s budget."""
    import asyncio

    now = 1000.0
    released = asyncio.Event()
    slept: list[float] = []

    async def slow_sleep(seconds: float) -> None:
        slept.append(seconds)
        await released.wait()  # B stays asleep until the test lets it go

    limiter = RateLimiter(min_interval=2.0, clock=lambda: now, sleep=slow_sleep)
    await limiter.acquire(deadline=now + 10)  # A: slot now
    b = asyncio.create_task(limiter.acquire(deadline=now + 10))  # B: slot now + 2
    await asyncio.sleep(0)
    assert slept == [pytest.approx(2.0)]
    with pytest.raises(SourceUnavailable):
        await asyncio.wait_for(limiter.acquire(deadline=now + 3), timeout=1)  # C: slot now + 4
    assert slept == [pytest.approx(2.0)]  # C never slept
    d = asyncio.create_task(limiter.acquire(deadline=now + 10))  # D takes the slot C didn't
    await asyncio.sleep(0)
    assert slept == [pytest.approx(2.0), pytest.approx(4.0)]
    released.set()
    await asyncio.gather(b, d)


async def test_a_late_waker_still_leaves_a_full_interval() -> None:
    """PR #26 review: B is planned for t+2 but wakes at t+3.4 (a busy loop); the next
    request still goes out at least 2 s after B actually did."""
    time = FakeTime()
    late = {"extra": 1.4}

    async def oversleep(seconds: float) -> None:
        time.slept.append(seconds)
        time.now += seconds + late.pop("extra", 0.0)

    limiter = RateLimiter(min_interval=2.0, clock=time.clock, sleep=oversleep)
    await limiter.acquire(deadline=time.now + 10)  # A at 1000
    await limiter.acquire(deadline=time.now + 10)  # B planned 1002, wakes 1003.4
    b_sent = time.now
    await limiter.acquire(deadline=time.now + 10)  # C
    assert time.now - b_sent >= 2.0 - 1e-9


async def test_a_cancelled_waiter_gives_its_slot_back() -> None:
    """PR #26 review: a request cancelled while waiting frees its slot when nothing was
    booked after it, so the next caller isn't pushed past its deadline."""
    import asyncio

    now = 1000.0

    async def forever(seconds: float) -> None:
        await asyncio.Event().wait()

    limiter = RateLimiter(min_interval=2.0, clock=lambda: now, sleep=forever)
    await limiter.acquire(deadline=now + 10)  # A: slot now, next free now + 2
    b = asyncio.create_task(limiter.acquire(deadline=now + 10))  # B: slot now + 2
    await asyncio.sleep(0)
    b.cancel()
    with pytest.raises(asyncio.CancelledError):
        await b
    # C may take B's slot again: now + 2 fits a 2.5 s deadline; now + 4 would not.
    c = asyncio.create_task(limiter.acquire(deadline=now + 2.5))
    await asyncio.sleep(0)
    assert not c.done()  # waiting for now + 2, not refused
    c.cancel()
