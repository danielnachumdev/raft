"""InPlaceDeployment unit paths (fakes only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from raft.core.core.models.app import App
from raft.core.lifecycle.deploy.methods.strategies.inplace import InPlaceDeployment
from raft.core.lifecycle.deploy.methods.method import DeploymentContext

from tests.unit.base import RaftTestCase


class TestInPlaceDeployment(RaftTestCase):
    def test_type_id(self) -> None:
        assert InPlaceDeployment().type_id == "inplace"

    def test_deploy_when_up_builds_before_stop_local(self, tmp_path: Path) -> None:
        from raft.core.core.models.state.redeploying_store import RedeployingStore

        ctx = self._ctx(tmp_path, source="local")
        order = self._track_prepare_stop_recreate(ctx, prepare="build_services")
        InPlaceDeployment().deploy_when_up(ctx)
        assert order == ["build", "stop", "recreate"]
        self._assert_local_prepare_path(ctx)
        assert not RedeployingStore(tmp_path).is_redeploying("demo-api")

    def test_deploy_when_up_keeps_live_on_prepare_failure(self, tmp_path: Path) -> None:
        from raft.core.core.models.state.redeploying_store import RedeployingStore

        ctx = self._ctx(tmp_path, source="local")
        ctx.support.docker.build_services.side_effect = RuntimeError("build boom")
        try:
            InPlaceDeployment().deploy_when_up(ctx)
        except RuntimeError:
            pass
        ctx.support.docker.stop_service.assert_not_called()
        ctx.support.docker.recreate_service.assert_not_called()
        assert not RedeployingStore(tmp_path).is_redeploying("demo-api")

    def test_deploy_when_up_clears_marker_on_failure(self, tmp_path: Path) -> None:
        from raft.core.core.models.state.redeploying_store import RedeployingStore

        ctx = self._ctx(tmp_path, source="local")
        ctx.support.docker.stop_service.side_effect = RuntimeError("stop boom")
        try:
            InPlaceDeployment().deploy_when_up(ctx)
        except RuntimeError:
            pass
        assert not RedeployingStore(tmp_path).is_redeploying("demo-api")

    def test_deploy_when_up_pulls_before_stop_docker(self, tmp_path: Path) -> None:
        ctx = self._ctx(tmp_path, source="docker")
        ref_state = tmp_path / "ref"
        ref_state.write_text("# requested: v2\n", encoding="utf-8")
        ctx.support.stack.ref_state_file.return_value = ref_state
        order = self._track_prepare_stop_recreate(ctx, prepare="prepare_pulled_image")
        InPlaceDeployment().deploy_when_up(ctx)
        assert order == ["pull", "stop", "recreate"]
        self._assert_docker_prepare_path(ctx)

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

    def _track_prepare_stop_recreate(
        self, ctx: DeploymentContext, *, prepare: str
    ) -> list[str]:
        order: list[str] = []
        label = "build" if prepare == "build_services" else "pull"
        getattr(ctx.support.docker, prepare).side_effect = (
            lambda *_a, **_k: order.append(label)
        )
        ctx.support.docker.stop_service.side_effect = lambda *_a, **_k: order.append(
            "stop"
        )
        ctx.support.docker.recreate_service.side_effect = lambda *_a, **_k: order.append(
            "recreate"
        )
        return order

    def _assert_local_prepare_path(self, ctx: DeploymentContext) -> None:
        ctx.support.nginx.point_absent.assert_called_once_with(ctx.app, reload=True)
        ctx.support.docker.build_services.assert_called_once_with(("demo-api",))
        ctx.support.docker.recreate_service.assert_called_once_with("demo-api")
        ctx.support.docker.rebuild_service.assert_not_called()
        ctx.support.docker.prepare_pulled_image.assert_not_called()
        ctx.support.finish_app_deploy.assert_called_once()

    def _assert_docker_prepare_path(self, ctx: DeploymentContext) -> None:
        ctx.support.nginx.point_absent.assert_called_once_with(ctx.app, reload=True)
        pull_ref = ctx.support.docker.prepare_pulled_image.call_args.kwargs["pull_ref"]
        assert pull_ref.endswith(":v2") or "v2" in pull_ref
        ctx.support.docker.recreate_pulled_service.assert_not_called()

    def _ctx(self, tmp_path: Path, *, source: str) -> DeploymentContext:
        app = App(
            name="demo-api",
            public_host="demo.test",
            source=source,
            path="services/x/checkout",
            image="ghcr.io/example/demo" if source == "docker" else None,
            ref="main",
        )
        support = MagicMock()
        support.stack.root = tmp_path
        support.stack.ref_state_file.return_value = tmp_path / "missing"
        return DeploymentContext(support=support, app=app, force_sync=True)
