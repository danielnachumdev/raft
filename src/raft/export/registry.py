"""Format-id lookup for exporters (open for new classes, closed for callers)."""

from .exporter import Exporter
from .unknown_format import UnknownExportFormat


class ExportRegistry:
    """Maps format id → exporter. Callers use catalog/get only."""

    def __init__(self) -> None:
        self._items: dict[str, Exporter] = {}

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

    def catalog(self) -> list[dict[str, str]]:
        return [item.spec.catalog_entry() for item in self._items.values()]
