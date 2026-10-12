"""Outcome of one channel delivery attempt."""

from enum import Enum


class DeliveryStatus(str, Enum):
    """Outcome of one channel delivery attempt."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
