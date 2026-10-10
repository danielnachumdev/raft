"""Fixed-period interval schedule."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .cron import CronSchedule
from .schedule import Schedule


class IntervalSchedule(Schedule):
    """Fixed period in seconds (sub-minute and non-minute intervals stay here)."""

    def __init__(self, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError(f"interval_seconds must be > 0, got {interval_seconds}")
        self.interval_seconds = float(interval_seconds)

    def next_fire_after(self, when: datetime) -> datetime:
        return when + timedelta(seconds=self.interval_seconds)

    def describe(self) -> str:
        return f"every {self.interval_seconds:g}s"

    def as_cron(self) -> Optional[CronSchedule]:
        """Map whole-minute intervals only (e.g. 60s → ``*/1 * * * *``)."""
        seconds = self.interval_seconds
        if seconds < 60 or seconds % 60 != 0:
            return None
        minutes = int(seconds // 60)
        if minutes < 60:
            return CronSchedule(f"*/{minutes} * * * *")
        if minutes % 60 == 0 and minutes // 60 < 24:
            return CronSchedule(f"0 */{minutes // 60} * * *")
        return None
