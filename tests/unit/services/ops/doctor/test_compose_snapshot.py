"""Doctor reuses one batched compose status across runtime + edge."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.adapters.docker.compose_status import ComposeStatusTable
from raft.models.stack import load_stack
from raft.services.ops.doctor.checks.edge import EdgeChecks
from raft.services.ops.doctor.checks.runtime import RuntimeChecks
from raft.services.ops.doctor.context import DoctorContext
from tests.shared.compose_ids import RunningServices

from ....base import write_applied_app
from .base import DoctorTestCase


class TestDoctorComposeSnapshot(DoctorTestCase):
    def test_runtime_and_edge_share_one_compose_status_call(self) -> None:
        ctx, docker = self._ctx_with_batch()
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("socket.create_connection", side_effect=OSError()):
                RuntimeChecks().run(ctx)
                EdgeChecks().run(ctx)
        assert docker.compose_service_status.call_count == 1
        docker.running_services.assert_not_called()
        docker.service_runtime.assert_not_called()

    def _ctx_with_batch(self):
        write_applied_app(self.tmp_path, "app")
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: null\n  streams: []\n",
            encoding="utf-8",
        )
        names = RunningServices.with_apps("app")
        docker = MagicMock()
        docker.compose_service_status.return_value = ComposeStatusTable.from_runtime_map(
            {name: ("running", "none") for name in names}
        )
        docker.gate_published_ports.return_value = [80]
        ctx = DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=docker,
        )
        return ctx, docker
