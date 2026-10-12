"""Exporter ABC — subclass + register to add a download format."""

from abc import ABC, abstractmethod
from typing import Any

from .spec import ExportSpec


class Exporter(ABC):
    """Strategy for encoding an export payload. Subclass + register to add a format."""

    def __init__(self, spec: ExportSpec) -> None:
        self.spec = spec

    @abstractmethod
    def encode(self, payload: Any) -> bytes:
        """Turn a domain payload into file bytes."""
