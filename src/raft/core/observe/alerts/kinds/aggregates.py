"""Numeric aggregates for threshold kind."""

from typing import List, Optional, Sequence


class Aggregates:
    """Apply named aggregate to numeric samples."""

    NAMES = ("avg", "min", "max", "sum", "last")

    @classmethod
    def apply(cls, name: str, values: Sequence[float]) -> Optional[float]:
        if not values:
            return None
        if name == "avg":
            return sum(values) / len(values)
        if name == "min":
            return min(values)
        if name == "max":
            return max(values)
        if name == "sum":
            return float(sum(values))
        if name == "last":
            return float(values[-1])
        raise ValueError(f"unknown aggregate {name!r}")
