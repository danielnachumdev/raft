"""Queryable schedules: interval (any period) and 5-field cron (minute resolution)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Set


class Schedule(ABC):
    """Next-fire query for orchestrator registration."""

    @abstractmethod
    def next_fire_after(self, when: datetime) -> datetime:
        """Strictly after ``when``."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable label for logs."""


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

    def as_cron(self) -> Optional["CronSchedule"]:
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


class CronSchedule(Schedule):
    """Standard 5-field cron: minute hour dom month dow (no seconds field)."""

    def __init__(self, expression: str) -> None:
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"cron expression must have 5 fields (got {len(parts)}): {expression!r}"
            )
        self.expression = " ".join(parts)
        self._minute = _CronField("minute", 0, 59, parts[0])
        self._hour = _CronField("hour", 0, 23, parts[1])
        self._dom = _CronField("dom", 1, 31, parts[2])
        self._month = _CronField("month", 1, 12, parts[3])
        self._dow = _CronField("dow", 0, 6, parts[4])

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


class _CronField:
    """Parsed cron field covering ``*``, ``N``, ``N-M``, ``*/N``, comma lists."""

    def __init__(self, name: str, minimum: int, maximum: int, raw: str) -> None:
        self.name = name
        self.minimum = minimum
        self.maximum = maximum
        self.values = self._parse(raw)

    def matches(self, value: int) -> bool:
        return value in self.values

    def _parse(self, raw: str) -> Set[int]:
        values: Set[int] = set()
        for part in raw.split(","):
            values.update(self._parse_part(part.strip()))
        if not values:
            raise ValueError(f"empty cron {self.name} field: {raw!r}")
        return values

    def _parse_part(self, part: str) -> List[int]:
        if not part:
            return []
        if part == "*":
            return list(range(self.minimum, self.maximum + 1))
        if part.startswith("*/"):
            return self._step_all(part[2:])
        if "-" in part:
            return self._range(part)
        return [self._bound(int(part))]

    def _step_all(self, step_raw: str) -> List[int]:
        step = int(step_raw)
        if step < 1:
            raise ValueError(f"cron {self.name} step must be >= 1, got {step}")
        return list(range(self.minimum, self.maximum + 1, step))

    def _range(self, part: str) -> List[int]:
        left, right = part.split("-", 1)
        start, end = self._bound(int(left)), self._bound(int(right))
        if start > end:
            raise ValueError(f"cron {self.name} range inverted: {part!r}")
        return list(range(start, end + 1))

    def _bound(self, value: int) -> int:
        if value < self.minimum or value > self.maximum:
            raise ValueError(
                f"cron {self.name} value {value} out of range "
                f"[{self.minimum}, {self.maximum}]"
            )
        return value
