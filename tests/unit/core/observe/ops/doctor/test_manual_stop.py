"""Doctor treats intentional manual-stop as OK, not missing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.doctor import INFRA
from raft.core.observe.ops.doctor.checks.public_host import PublicHostChecks
from raft.core.observe.ops.doctor.checks.runtime import RuntimeChecks
from raft.core.observe.ops.doctor.context import DoctorContext
from tests.shared.compose_ids import RunningServices
from tests.unit.base import AppliedInventory
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase
from tests.unit.core.observe.ops.doctor.fixtures import wire_labeled_docker_ps


class TestDoctorManualStop(DoctorTestCase):
    def _ctx(self, docker: MagicMock) -> DoctorContext:
        AppliedInventory.write_applied_app(self.tmp_path, "app")
        ctx = DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=docker,
        )
        wire_labeled_docker_ps(ctx.shell, docker)
        return ctx

    def test_runtime_excludes_manual_stop_from_missing(self) -> None:
        docker = self.mock_docker(running=RunningServices.edge())
        ManualStopStore(self.tmp_path).mark("app")
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[(INFRA, "stack")].status == "ok"
        assert results[("app", "lifecycle")].status == "ok"
        assert "manual stop" in results[("app", "lifecycle")].detail
        assert "app" not in (results[(INFRA, "stack")].detail or "")

    def test_public_host_ok_when_manual_stop(self) -> None:
        docker = MagicMock()
        ManualStopStore(self.tmp_path).mark("app")
        ctx = self._ctx(docker)
        with patch(
            "raft.core.observe.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ) as probe:
            results = PublicHostChecks().run(ctx)
        assert results[0].status == "ok"
        assert "manual stop" in results[0].detail
        probe.assert_not_called()
