"""Doctor fails running-but-unhealthy / restarting containers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.adapters.docker.compose_status import ComposeStatusTable
from raft.models.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.ops.doctor.checks.runtime import RuntimeChecks
from raft.services.ops.doctor.context import DoctorContext
from tests.shared.compose_ids import RunningServices

from ....base import write_applied_app
from .base import DoctorTestCase


class TestDoctorHealth(DoctorTestCase):
    def _ctx(self, docker: MagicMock) -> DoctorContext:
        write_applied_app(self.tmp_path, "app")
        return DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=docker,
        )

    def test_edge_fails_when_unhealthy(self) -> None:
        docker = self.mock_docker(
            running=RunningServices.edge(),
            runtime={
                "raft-gate": ("running", "unhealthy"),
                "raft-router": ("running", "unhealthy"),
            },
        )
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[("raft-gate", "running")].status == "fail"
        assert results[("raft-gate", "running")].detail == "unhealthy"
        assert results[("raft-router", "running")].status == "fail"

    def test_app_fails_when_unhealthy(self) -> None:
        docker = self.mock_docker(
            running=RunningServices.with_apps("app"),
            runtime={
                "raft-gate": ("running", "healthy"),
                "raft-router": ("running", "none"),
                "app": ("running", "unhealthy"),
            },
        )
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[("raft-gate", "running")].status == "ok"
        assert results[("app", "running")].status == "fail"
        assert results[("app", "running")].detail == "unhealthy"

    def test_app_warns_when_health_starting(self) -> None:
        docker = self.mock_docker(
            running=RunningServices.with_apps("app"),
            runtime={"app": ("running", "starting")},
        )
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[("app", "running")].status == "warn"
        assert "starting" in results[("app", "running")].detail

    def test_restarting_fails(self) -> None:
        docker = self.mock_docker(running=RunningServices.edge())
        docker.compose_service_status.return_value = ComposeStatusTable.from_runtime_map(
            {
                "raft-gate": ("running", "none"),
                "raft-router": ("running", "none"),
                "app": ("restarting", "none"),
            }
        )
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert results[("app", "running")].status == "fail"
        assert results[("app", "running")].detail == "restarting"

    def test_scaled_to_zero_skips_health(self) -> None:
        docker = self.mock_docker(running=RunningServices.edge())
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        ctx = self._ctx(docker)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
        assert ("app", "running") not in results
        assert results[("app", "scaling")].status == "ok"
