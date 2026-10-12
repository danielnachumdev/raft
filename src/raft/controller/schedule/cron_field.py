"""Parsed single cron field covering ``*``, ``N``, ``N-M``, ``*/N``, comma lists."""

from typing import List, Set


class CronField:
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
