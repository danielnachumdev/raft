"""Doctor treats intentional scale-to-zero as OK, not missing/unhealthy."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from raft.models.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.ops.doctor import INFRA, CheckResult
from raft.services.ops.doctor.checks.public_host import PublicHostChecks
from raft.services.ops.doctor.checks.runtime import RuntimeChecks
from raft.services.ops.doctor.context import DoctorContext
from raft.services.ops.doctor.report import GroupReportWriter
from tests.shared.compose_ids import RunningServices

from ....base import write_applied_app
from .base import DoctorTestCase


class TestDoctorScaledToZero(DoctorTestCase):
    def _ctx(self, docker: MagicMock) -> DoctorContext:
        write_applied_app(self.tmp_path, "app")
        return DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=docker,
        )

    def test_runtime_excludes_scaled_app_from_missing(self) -> None:
        docker = self.mock_docker(running=RunningServices.edge())
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[(INFRA, "stack")].status == "ok"
        assert results[("app", "scaling")].status == "ok"
        assert "intentional" in results[("app", "scaling")].detail
        assert "app" not in (results[(INFRA, "stack")].detail or "")

    def test_runtime_still_warns_when_unscaled_app_missing(self) -> None:
        docker = self.mock_docker(running=RunningServices.edge())
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[(INFRA, "stack")].status == "warn"
        assert "app" in results[(INFRA, "stack")].detail
        assert ("app", "scaling") not in results

    def test_public_host_ok_when_scaled_to_zero(self) -> None:
        docker = MagicMock()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        ctx = self._ctx(docker)
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ) as probe:
            results = PublicHostChecks().run(ctx)
        assert results[0].status == "ok"
        assert "scaled to zero" in results[0].detail
        probe.assert_not_called()

    def test_report_shows_scaling_note_on_ok_line(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stack = load_stack(self.tmp_path)
        out = StringIO()
        results = [
            CheckResult("app", "scaling", "ok", "scaled to zero (intentional)"),
            CheckResult("app", "ports", "ok", "80"),
        ]
        assert GroupReportWriter().write(stack, results, out=out, color=False) == 0
        text = out.getvalue()
        assert "scaled to zero (intentional)" in text
