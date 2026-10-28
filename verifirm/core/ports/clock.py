"""Clock port, so tests and the demo can pin "now"."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Timezone-aware UTC now."""

    def today(self) -> date:
        return self.now().date()
