"""Export registry: lookup, catalog, open-closed register."""

from __future__ import annotations

from typing import Any

from raft.export.catalogs import ExportCatalogs
from raft.export.format import Exporter, ExportSpec
from raft.export.strategies.metrics_delimited import DelimitedMetricsExporter
from raft.export.registry import ExportRegistry, UnknownExportFormat

from tests.unit.base import RaftTestCase


class _StubExporter(Exporter):
    def __init__(self, format_id: str) -> None:
        super().__init__(
            ExportSpec(format_id, format_id.upper(), "text/plain", format_id)
        )

    def encode(self, payload: Any) -> bytes:
        return b"stub"


class TestExportRegistry(RaftTestCase):
    def test_catalog_lists_registered_order(self) -> None:
        registry = ExportRegistry()
        registry.register(_StubExporter("a"))
        registry.register(_StubExporter("b"))
        assert [row["id"] for row in registry.catalog()] == ["a", "b"]

    def test_get_unknown_lists_known_ids(self) -> None:
        registry = ExportRegistry()
        registry.register(_StubExporter("csv"))
        try:
            registry.get("xlsx")
        except UnknownExportFormat as exc:
            assert "xlsx" in str(exc) and "csv" in str(exc)
        else:
            raise AssertionError("expected UnknownExportFormat")

    def test_duplicate_register_is_rejected(self) -> None:
        registry = ExportRegistry()
        registry.register(_StubExporter("txt"))
        try:
            registry.register(_StubExporter("txt"))
        except ValueError as exc:
            assert "duplicate" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_new_format_is_visible_without_replacing_callers(self) -> None:
        registry = ExportCatalogs.metrics()
        before = {row["id"] for row in registry.catalog()}
        registry.register(DelimitedMetricsExporter.tsv())
        after = {row["id"] for row in registry.catalog()}
        assert before == {"csv"}
        assert after == {"csv", "tsv"}
        assert registry.get("tsv").spec.suffix == "tsv"


class TestShippedCatalogs(RaftTestCase):
    def test_logs_ship_txt_and_json(self) -> None:
        ids = [row["id"] for row in ExportCatalogs.logs().catalog()]
        assert ids == ["txt", "json"]

    def test_metrics_ship_csv_only(self) -> None:
        ids = [row["id"] for row in ExportCatalogs.metrics().catalog()]
        assert ids == ["csv"]
