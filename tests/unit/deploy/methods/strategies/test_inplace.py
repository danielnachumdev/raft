"""InPlaceDeployment unit paths (fakes only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from raft.models.app import App
from raft.deploy.methods.strategies.inplace import InPlaceDeployment
from raft.deploy.methods.method import DeploymentContext

from tests.unit.base import RaftTestCase


class TestInPlaceDeployment(RaftTestCase):
    def test_type_id(self) -> None:
        assert InPlaceDeployment().type_id == "inplace"

    def test_deploy_when_up_rebuilds_local(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="local")
        InPlaceDeployment().deploy_when_up(ctx)
        ctx.support.docker.stop_service.assert_called_once_with("demo-api")
        ctx.support.docker.rebuild_service.assert_called_once_with("demo-api")
        ctx.support.docker.recreate_pulled_service.assert_not_called()
        ctx.support.finish_app_deploy.assert_called_once()

    def test_deploy_when_up_recreates_docker(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="docker")
        ref_state = tmp_path / "ref"
        ref_state.write_text("# requested: v2\n", encoding="utf-8")
        ctx.support.stack.ref_state_file.return_value = ref_state
        InPlaceDeployment().deploy_when_up(ctx)
        ctx.support.docker.recreate_pulled_service.assert_called_once()
        pull_ref = ctx.support.docker.recreate_pulled_service.call_args.kwargs["pull_ref"]
        assert pull_ref.endswith(":v2") or "v2" in pull_ref

    def test_wanted_tag_falls_back_without_state(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="docker")
        ctx.support.stack.ref_state_file.return_value = tmp_path / "missing"
        assert InPlaceDeployment()._wanted_tag(ctx) == "main"

    def test_wanted_tag_ignores_unrelated_lines(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="docker")
        ref_state = tmp_path / "ref"
        ref_state.write_text("abc\n# other: x\n", encoding="utf-8")
        ctx.support.stack.ref_state_file.return_value = ref_state
        assert InPlaceDeployment()._wanted_tag(ctx) == "main"

    def test_deploy_when_down_delegates(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="local")
        InPlaceDeployment().deploy_when_down(ctx)
        ctx.support.deploy_single_generation.assert_called_once()

    def _ctx(self, tmp_path: Path, *, source: str) -> DeploymentContext:
        app = App(
            name="demo-api",
            public_host="demo.test",
            source=source,
            path="apps/x",
            image="ghcr.io/example/demo" if source == "docker" else None,
            ref="main",
        )
        support = MagicMock()
        support.stack.root = tmp_path
        support.stack.ref_state_file.return_value = tmp_path / "missing"
        return DeploymentContext(support=support, app=app, force_sync=True)
