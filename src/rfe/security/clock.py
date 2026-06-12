"""Clock port + adapters. Injecting the clock keeps time-dependent logic
(token expiry, audit timestamps) deterministic in tests; no datetime.now()
buried in domain/use-case code."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time, timezone-aware (UTC)."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Test double: returns a fixed, settable time."""

    def __init__(self, fixed: datetime):
        self._now = fixed

    def now(self) -> datetime:
        return self._now

    def set(self, fixed: datetime) -> None:
        self._now = fixed
