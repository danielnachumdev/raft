"""Runtime suite reads labeled docker ps, not compose ps."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.doctor.checks.edge import EdgeChecks
from raft.core.observe.ops.doctor.checks.runtime import RuntimeChecks
from raft.core.observe.ops.doctor.context import DoctorContext

from tests.unit.base import AppliedInventory
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase


class TestDoctorRuntimeDockerPs(DoctorTestCase):
    def test_runtime_uses_labeled_docker_ps_not_compose(self) -> None:
        ctx, docker, shell = self._ctx()
        with patch("shutil.which", return_value="/usr/bin/docker"):
            results = {(r.service, r.check): r for r in RuntimeChecks().run(ctx)}
            EdgeChecks().run(ctx)
        self._assert_engine_path(docker, shell, results)

    def _assert_engine_path(self, docker, shell, results) -> None:
        docker.compose_service_status.assert_not_called()
        docker.running_services.assert_not_called()
        docker.service_runtime.assert_not_called()
        ps_calls = [c for c in shell.docker.call_args_list if c.args[:1] == ("ps",)]
        assert len(ps_calls) == 1
        assert "label=com.docker.compose.project=raft" in ps_calls[0].args
        assert all(c.args[:1] != ("stats",) for c in shell.docker.call_args_list)
        assert results[("raft-gate", "running")].status == "ok"
        assert results[("app", "running")].detail == "unhealthy"
        assert results[("raft-controller", "running")].detail == "restarting"

    def _ctx(self):
        AppliedInventory.write_applied_app(self.tmp_path, "app")
        docker = MagicMock()
        shell = MagicMock()
        shell.docker.side_effect = self._engine
        ctx = DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=shell,
            auth=MagicMock(),
            docker=docker,
        )
        return ctx, docker, shell

    def _engine(self, *args, **kwargs):
        del kwargs
        if args[:1] == ("ps",):
            return self._ok(self._ps_stdout())
        if args[:1] == ("inspect",):
            return self._ok(json.dumps(self._inspect_payload()))
        raise AssertionError(f"unexpected docker args: {args!r}")

    @staticmethod
    def _ok(stdout: str) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        result.stdout = stdout
        result.stderr = ""
        return result

    @staticmethod
    def _ps_stdout() -> str:
        return "gateid\traft-gate\nrouterid\traft-router\nctrlid\traft-controller\nappid\tapp\n"

    @staticmethod
    def _inspect_payload() -> list:
        return [
            _inspect("gateid", "running", None),
            _inspect("routerid", "running", None),
            _inspect("ctrlid", "restarting", None),
            _inspect("appid", "running", "unhealthy"),
        ]


def _inspect(cid: str, status: str, health: str | None) -> dict:
    state: dict = {"Status": status, "StartedAt": "2024-01-01T00:00:00Z", "OOMKilled": False}
    if health is not None:
        state["Health"] = {"Status": health}
    return {"Id": cid, "RestartCount": 0, "State": state, "HostConfig": {}}
