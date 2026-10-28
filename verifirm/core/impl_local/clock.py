from __future__ import annotations

from datetime import UTC, datetime

from verifirm.core.ports.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """Pinned clock for tests and reproducible demos."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self.at = at

    def now(self) -> datetime:
        return self.at
