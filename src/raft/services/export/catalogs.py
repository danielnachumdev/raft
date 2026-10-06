"""Shipped export catalogs. Add a format by registering another Exporter."""

from __future__ import annotations

from .logs_json import LogsJsonExporter
from .logs_txt import LogsTxtExporter
from .metrics_delimited import DelimitedMetricsExporter
from .registry import ExportRegistry


class ExportCatalogs:
    """Composition root for download formats (UI/API read catalog() only).

    Add TSV with ``registry.register(DelimitedMetricsExporter.tsv())``.
    Add XLSX with a new ``Exporter`` subclass (do not grow this class's
    encode logic) and ``registry.register(XlsxMetricsExporter())``.
    """

    @staticmethod
    def logs() -> ExportRegistry:
        registry = ExportRegistry()
        registry.register(LogsTxtExporter())
        registry.register(LogsJsonExporter())
        return registry

    @staticmethod
    def metrics() -> ExportRegistry:
        registry = ExportRegistry()
        registry.register(DelimitedMetricsExporter.csv())
        return registry
