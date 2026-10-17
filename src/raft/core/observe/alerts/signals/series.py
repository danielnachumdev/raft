"""Signal time series types."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Tuple


class ValueType(str, Enum):
    NUMERIC = "numeric"
    STATE = "state"
    EVENT = "event"


@dataclass(frozen=True)
class SignalPoint:
    ts: datetime
    value: Any


@dataclass(frozen=True)
class SubjectSeries:
    subject: str
    points: Tuple[SignalPoint, ...]
    wildcard: bool = False
