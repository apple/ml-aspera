#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from abc import ABC, abstractmethod
from asyncio import sleep
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from types import TracebackType

from pyrate_limiter import Limiter, Rate

logger = logging.getLogger(__name__)

TimeGetter = Callable[[], datetime]


def _default_time_getter() -> datetime:
    return datetime.now()


class RateLimiter(ABC):
    @abstractmethod
    async def try_consume(self, num_tokens: int) -> None: ...

    @abstractmethod
    def consume(self, num_tokens: int) -> None: ...


class TokenUsageRateLimiter(RateLimiter):
    def __init__(self, rate: Rate, time_getter: TimeGetter | None = None) -> None:
        self._time_getter: TimeGetter = (
            _default_time_getter if time_getter is None else time_getter
        )
        self._capacity = rate.limit
        self._time_window_duration = timedelta(seconds=rate.interval)
        self._calls: deque[tuple[datetime, int]] = deque()

    async def try_consume(self, num_tokens: int) -> None:
        while True:
            now = self._time_getter()
            while self._calls and (
                now - self._calls[0][0] > self._time_window_duration
            ):
                self._calls.popleft()

            num_used_tokens = sum([call[1] for call in self._calls])
            total_used_tokens = num_used_tokens + num_tokens
            if total_used_tokens > self._capacity:
                current_span = now - self._calls[0][0]
                time_until_next_span = (
                    self._time_window_duration - current_span
                ).seconds

                extra_consumption = total_used_tokens - self._capacity
                refill_rate = self._capacity / self._time_window_duration.seconds
                extra_time_until_refilled = extra_consumption / refill_rate
                sleep_time = time_until_next_span + extra_time_until_refilled

                logger.debug(
                    f"Tried to consume {num_tokens} with capacity={self._capacity} and "
                    f"{num_used_tokens} already used in time window. "
                    f"Sleeping for {sleep_time}s"
                )
                await sleep(sleep_time)
            else:
                # currently enough capacity in this time window so go ahead
                self.consume(num_tokens)
                break

    def consume(self, num_tokens: int) -> None:
        self._calls.append((self._time_getter(), num_tokens))


class NoopRateLimiter(RateLimiter):
    async def try_consume(self, num_tokens: int) -> None:
        del num_tokens

    def consume(self, num_tokens: int) -> None:
        del num_tokens

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type, exc_val, exc_tb


class NoopLimiter(Limiter):
    def ratelimit(
        self,
        *identities: str,
        delay: bool = False,
        max_delay: int | float | None = None,
    ) -> RateLimiter:
        del identities, delay, max_delay
        return NoopRateLimiter()
