"""Format-id lookup for exporters (open for new classes, closed for callers)."""

from __future__ import annotations

from typing import Dict, List

from .format import Exporter


class UnknownExportFormat(ValueError):
    """Raised when a download requests a format the registry does not have."""

    def __init__(self, format_id: str, known: List[str]) -> None:
        listed = ", ".join(known) if known else "(none)"
        super().__init__(
            f"unknown export format '{format_id}' (known: {listed})"
        )
        self.format_id = format_id
        self.known = known


class ExportRegistry:
    """Maps format id → exporter. Callers use catalog/get only."""

    def __init__(self) -> None:
        self._items: Dict[str, Exporter] = {}

    def register(self, exporter: Exporter) -> None:
        fid = exporter.spec.format_id
        if fid in self._items:
            raise ValueError(f"duplicate export format '{fid}'")
        self._items[fid] = exporter

    def get(self, format_id: str) -> Exporter:
        try:
            return self._items[format_id]
        except KeyError:
            raise UnknownExportFormat(format_id, list(self._items)) from None

    def catalog(self) -> List[Dict[str, str]]:
        return [item.spec.catalog_entry() for item in self._items.values()]
