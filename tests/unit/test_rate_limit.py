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
