"""Status human/JSON report coverage."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from raft.services.ops.status import Status
from raft.services.ops.status.models import AllocatedResources
from raft.services.ops.status.report import write_report

from ....base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatusFixtures


class TestStatusReportHuman(RaftTestCase):
    def _stopped_snapshot(self):
        write_applied_app(self.tmp_path, "app")
        status = Status(make_stack(self.tmp_path, (make_app("app"),)))
        StatusFixtures.mock_docker_idle(status)
        with patch(
            "raft.services.ops.status.service.collect_host_resources",
            return_value=StatusFixtures.host(),
        ):
            return status, status.collect()

    def test_report_human_and_json(self) -> None:
        status, snap = self._stopped_snapshot()
        self._assert_human(snap)
        self._assert_json(snap)
        with patch.object(status, "collect", return_value=snap):
            assert status.report(as_json=False) == 0

    def _assert_human(self, snap) -> None:
        out = StringIO()
        assert write_report(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert "Host" in text and "Containers" in text
        assert "NAME" in text and "GROUP" in text
        assert "gate" in text and "raft-gate" not in text
        assert text.index("NAME") < text.index("GROUP")
        gate_line = next(line for line in text.splitlines() if line.strip().startswith("gate "))
        assert "raft" in gate_line.split()
        assert "CPUs: 4" in text

    def _assert_json(self, snap) -> None:
        jout = StringIO()
        assert write_report(snap, as_json=True, out=jout) == 0
        payload = json.loads(jout.getvalue())
        assert payload["host"]["cpus"] == 4
        assert payload["containers"][0]["service"] == "raft-gate"
        assert payload["containers"][0]["group"] == "raft"
        assert "allocated" in payload["containers"][0]

    def test_report_group_column(self) -> None:
        snap = StatusFixtures.snapshot(
            StatusFixtures.container("raft-gate", role="gate", group="raft", cpu=0.1),
            StatusFixtures.container("demo-web", app="web", group="demo"),
        )
        text = self._render(snap)
        self._assert_group_headers(text)
        self._assert_group_rows(text)

    def _render(self, snap) -> str:
        out = StringIO()
        assert write_report(snap, out=out, color=False) == 0
        return out.getvalue()

    def _assert_group_headers(self, text: str) -> None:
        header = next(line for line in text.splitlines() if "NAME" in line and "GROUP" in line)
        cols = header.split()
        assert cols.index("NAME") == 0 and cols.index("GROUP") == 1
        assert "raft-gate" not in text and "demo-web" not in text

    def _assert_group_rows(self, text: str) -> None:
        gate_line = next(line for line in text.splitlines() if line.strip().startswith("gate "))
        web_line = next(line for line in text.splitlines() if line.strip().startswith("web "))
        assert gate_line.split()[1] == "raft"
        assert web_line.split()[1] == "demo"

    def test_models_to_dict(self) -> None:
        allocated = AllocatedResources("0.5", "128M", "0.1", "32M")
        assert allocated.to_dict()["cpus_limit"] == "0.5"
        from raft.services.ops.status.models import IoPair, MemoryUsage

        assert IoPair(1, 2).to_dict()["rx_or_read_bytes"] == 1
        assert MemoryUsage(1, 2, 3.0).to_dict()["used_percent"] == 3.0

    def test_inspect_memory_fills_limit_and_bad_pids(self) -> None:
        from raft.services.ops.status.service import _container_from_row, _pids

        assert _pids(None) is None and _pids("nope") is None and _pids("7") == 7
        row = _container_from_row(
            service="app",
            role="app",
            app="app",
            group=None,
            allocated=AllocatedResources("0.5", "128M", "0.1", "32M"),
            status="running",
            uptime_seconds=10.0,
            stats_row={
                "CPUPerc": "1%",
                "MemUsage": "1MiB / --",
                "MemPerc": "1%",
                "NetIO": "0B / 0B",
                "BlockIO": "0B / 0B",
                "PIDs": "bad",
            },
            inspect_memory=67108864,
        )
        assert row.memory.limit_bytes == 67108864 and row.pids is None
