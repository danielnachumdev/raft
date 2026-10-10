"""Exporter contract: one format id, one encoder, one attachment type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class ExportSpec:
    """Stable catalog fields for one download format."""

    format_id: str
    label: str
    media_type: str
    suffix: str

    def catalog_entry(self) -> Dict[str, str]:
        return {
            "id": self.format_id,
            "label": self.label,
            "media_type": self.media_type,
            "suffix": self.suffix,
        }


class Exporter(ABC):
    """Strategy for encoding an export payload. Subclass + register to add a format."""

    def __init__(self, spec: ExportSpec) -> None:
        self.spec = spec

    @abstractmethod
    def encode(self, payload: Any) -> bytes:
        """Turn a domain payload into file bytes."""
