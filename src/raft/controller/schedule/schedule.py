"""Queryable schedule ABC for orchestrator registration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Schedule(ABC):
    """Next-fire query for orchestrator registration."""

    @abstractmethod
    def next_fire_after(self, when: datetime) -> datetime:
        """Strictly after ``when``."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable label for logs."""
