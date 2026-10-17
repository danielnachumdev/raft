"""Comparison operators for threshold / event_count."""

from typing import Any


class Comparison:
    """Apply a comparison operator."""

    OPS = ("gt", "gte", "lt", "lte", "eq", "ne")

    @classmethod
    def apply(cls, op: str, left: Any, right: Any) -> bool:
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        if op == "eq":
            return left == right
        if op == "ne":
            return left != right
        raise ValueError(f"unknown op {op!r}")
