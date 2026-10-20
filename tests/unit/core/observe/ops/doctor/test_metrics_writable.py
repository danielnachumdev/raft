"""Doctor fails when controller metrics JSONL is not writable."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.doctor.checks.host import HostChecks
from raft.core.observe.ops.doctor.context import DoctorContext
from raft.core.observe.ops.doctor.models import INFRA

from tests.unit.core.observe.ops.doctor.base import DoctorTestCase


class TestMetricsWritable(DoctorTestCase):
    def test_skips_when_metrics_dir_missing(self) -> None:
        # ensure_raft_home creates host/metrics; remove so parent.is_dir is false.
        metrics = self.tmp_path / "host" / "metrics"
        if metrics.exists():
            shutil.rmtree(metrics)
        assert not metrics.is_dir()
        assert HostChecks()._metrics(self._ctx()) is None

    def test_ok_when_active_file_writable(self) -> None:
        path = self._seed_metrics_file()
        assert path.is_file()
        assert HostChecks()._metrics(self._ctx()) is None

    def test_fails_when_active_file_not_writable(self) -> None:
        path = self._seed_metrics_file()
        with patch("raft.core.observe.ops.doctor.checks.host.os.access") as access:
            access.side_effect = self._deny_path(path)
            result = HostChecks()._metrics(self._ctx())
        assert result is not None
        assert result.service == INFRA and result.check == "metrics"
        assert result.status == "fail"
        assert "chown" in (result.fix or "")

    def test_fails_when_metrics_dir_not_writable(self) -> None:
        path = self._seed_metrics_file()
        parent = path.parent
        with patch("raft.core.observe.ops.doctor.checks.host.os.access") as access:
            access.side_effect = self._deny_path(parent)
            result = HostChecks()._metrics(self._ctx())
        assert result is not None and result.status == "fail"
        assert str(parent) in result.detail

    def _ctx(self) -> DoctorContext:
        return DoctorContext(
            stack=self.stack,
            shell=MagicMock(),
            auth=MagicMock(),
            docker=self.mock_docker(),
        )

    def _seed_metrics_file(self) -> Path:
        path = self.tmp_path / "host" / "metrics" / "resources.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    @staticmethod
    def _deny_path(blocked: Path):
        def _access(target, mode, **kwargs):
            return Path(target) != Path(blocked)

        return _access
