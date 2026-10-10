"""5-field cron schedule (minute resolution)."""

from __future__ import annotations

from datetime import datetime, timedelta

from .cron_field import CronField
from .schedule import Schedule


class CronSchedule(Schedule):
    """Standard 5-field cron: minute hour dom month dow (no seconds field)."""

    def __init__(self, expression: str) -> None:
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"cron expression must have 5 fields (got {len(parts)}): {expression!r}"
            )
        self.expression = " ".join(parts)
        self._minute = CronField("minute", 0, 59, parts[0])
        self._hour = CronField("hour", 0, 23, parts[1])
        self._dom = CronField("dom", 1, 31, parts[2])
        self._month = CronField("month", 1, 12, parts[3])
        self._dow = CronField("dow", 0, 6, parts[4])

    def next_fire_after(self, when: datetime) -> datetime:
        candidate = when.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = candidate + timedelta(days=366)
        while candidate <= limit:
            if self._matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError(f"no cron match within a year for {self.expression!r}")

    def describe(self) -> str:
        return f"cron {self.expression}"

    def _matches(self, when: datetime) -> bool:
        # cron DOW: Sun=0..Sat=6; Python weekday(): Mon=0..Sun=6
        cron_dow = (when.weekday() + 1) % 7
        return (
            self._minute.matches(when.minute)
            and self._hour.matches(when.hour)
            and self._dom.matches(when.day)
            and self._month.matches(when.month)
            and self._dow.matches(cron_dow)
        )
