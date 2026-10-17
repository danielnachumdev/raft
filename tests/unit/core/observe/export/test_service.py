"""ExportService encode + catalog (shared by serve + CLI)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.export.service import ExportService, MAX_LOG_TAIL
from raft.services.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME
from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestExportService(RaftTestCase):
    def test_catalog_and_encode_logs(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        logs = MagicMock()
        logs.snapshot.return_value = "hello\n"
        svc = ExportService(stack, logs=logs)
        catalog = svc.catalog()
        assert [r["id"] for r in catalog["logs"]] == ["txt", "json"]
        assert [r["id"] for r in catalog["metrics"]] == ["csv"]
        exporter, body, stem = svc.encode_logs("site", format_id="txt", tail=20)
        assert body == b"hello\n"
        assert stem == "raft-logs-site"
        assert exporter.spec.format_id == "txt"
        logs.snapshot.assert_called_once_with("site", tail=20)

    def test_encode_metrics_and_write(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        self._write_sample(stack.root)
        svc = ExportService(stack)
        _exporter, body, stem = svc.encode_metrics(format_id="csv", window=3600)
        assert stem == "raft-metrics"
        assert body.startswith(b"t,series_id,")
        out = Path(self.tmp_path) / "out.csv"
        ExportService.write_bytes(out, body)
        assert out.read_bytes() == body

    def _write_sample(self, root: Path) -> None:
        import json

        ts = datetime.now(timezone.utc).isoformat()
        path = root / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": ts,
            "host": {"cpus": 2, "loadavg": [1.0], "memory": {"used_percent": 10}},
            "containers": [
                {
                    "service": "raft-gate",
                    "role": "gate",
                    "group": "raft",
                    "cpu_percent": 4.0,
                    "memory": {"used_percent": 20},
                }
            ],
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    def test_unknown_format_and_split_clamp(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        logs = MagicMock()
        logs.snapshot.return_value = "x"
        svc = ExportService(stack, logs=logs)
        with pytest.raises(OperatorError, match="xlsx"):
            svc.encode_logs("site", format_id="xlsx")
        svc.encode_logs("site", tail=0)
        svc.encode_logs("site", tail=99999)
        assert logs.snapshot.call_args_list[0].kwargs["tail"] == 1
        assert logs.snapshot.call_args_list[1].kwargs["tail"] == MAX_LOG_TAIL
        assert ExportService.split_services(None) is None
        assert ExportService.split_services(" a, b ") == ["a", "b"]
