"""Metrics delimited table encoder (CSV shipped; TSV via same class)."""

from __future__ import annotations

from raft.export.strategies.metrics_delimited import DelimitedMetricsExporter

from tests.unit.base import RaftTestCase

_PAYLOAD = {
    "series": [
        {
            "id": "site",
            "label": "site",
            "kind": "container",
            "role": "app",
            "group": "demo",
            "points": [
                {
                    "t": "2026-01-01T00:00:00+00:00",
                    "cpu_percent": 1.5,
                    "memory_used_percent": 10,
                    "memory_used_bytes": 1024,
                    "memory_limit_bytes": None,
                }
            ],
        }
    ]
}


class TestDelimitedMetricsExporter(RaftTestCase):
    def test_csv_header_and_row(self) -> None:
        text = DelimitedMetricsExporter.csv().encode(_PAYLOAD).decode("utf-8")
        lines = text.strip().split("\n")
        assert lines[0].startswith("t,series_id,label,kind,role,group,")
        assert "site,site,container,app,demo,1.5,10,1024" in lines[1]

    def test_empty_payload_is_header_only(self) -> None:
        text = DelimitedMetricsExporter.csv().encode({}).decode("utf-8")
        assert text == ",".join(DelimitedMetricsExporter.COLUMNS) + "\n"

    def test_skips_non_dict_series_and_bad_points(self) -> None:
        payload = {
            "series": [
                "nope",
                {"id": "x", "points": "bad"},
                {
                    "id": "ok",
                    "label": "ok",
                    "kind": "container",
                    "role": "app",
                    "group": None,
                    "points": ["skip", {"t": "t1", "cpu_percent": 2}],
                },
            ]
        }
        text = DelimitedMetricsExporter.csv().encode(payload).decode("utf-8")
        lines = [ln for ln in text.split("\n") if ln]
        assert len(lines) == 2
        assert ",ok,ok,container,app,,2" in lines[1]

    def test_tsv_uses_tabs(self) -> None:
        text = DelimitedMetricsExporter.tsv().encode(_PAYLOAD).decode("utf-8")
        header = text.split("\n", 1)[0]
        assert "\t" in header and "," not in header
        assert header.startswith("t\tseries_id\t")
