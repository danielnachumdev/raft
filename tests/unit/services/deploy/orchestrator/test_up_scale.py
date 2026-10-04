"""``raft up`` skips starting scale-to-zero apps but still pulls images."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.models.state.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.deploy.orchestrator import Orchestrator
from tests.shared.compose_ids import RunningServices
from tests.unit.base import write_applied_app
from tests.unit.controller.base import ControllerTestCase

from .base import OrchestratorTestCase


class TestOrchUpScale(OrchestratorTestCase, ControllerTestCase):
    def test_start_skips_scaling_app_pulls_and_marks_zero(self) -> None:
        write_applied_app(self.tmp_path, "app", extra=self.scaling_extra())
        orch = self._orch_cold_edge()
        with patch.object(orch, "sync"):
            orch.start()
        # local/git deferred → build only (compose pull would be a no-op)
        orch.docker.pull_services.assert_called_once_with(())
        orch.docker.build_services.assert_called_once_with(("app",))
        orch.docker.start_stack.assert_called_once_with(
            ("raft-gate", "raft-router", "raft-controller")
        )
        assert ScalingStore(self.tmp_path).is_scaled_to_zero("app")

    def test_start_docker_scaling_app_pulls_without_empty_build(self) -> None:
        """Image-only deferred apps must not invoke ``compose build`` (Compose WARN)."""
        write_applied_app(
            self.tmp_path,
            "app",
            source="docker",
            image="ghcr.io/example/app",
            build_context=None,
            extra=self.scaling_extra(),
        )
        orch = self._orch_cold_edge()
        with patch.object(orch, "sync"):
            orch.start()
        orch.docker.pull_services.assert_called_once_with(("app",))
        orch.docker.build_services.assert_called_once_with(())
        assert ScalingStore(self.tmp_path).is_scaled_to_zero("app")

    def test_start_parks_deferred_upstreams_before_router(self) -> None:
        """Awake-then-down scaling apps must be parked before compose starts router."""
        write_applied_app(self.tmp_path, "app", extra=self.scaling_extra())
        orch = self._orch_cold_edge()
        order: list[str] = []

        def on_park(app, *, reload: bool = False) -> None:
            order.append(f"park:{app.name}")

        def on_start(*_args, **_kwargs) -> None:
            assert ScalingStore(self.tmp_path).is_scaled_to_zero("app")
            order.append("start")

        orch.nginx.point_absent.side_effect = on_park
        orch.docker.start_stack.side_effect = on_start
        with patch.object(orch, "sync"):
            orch.start()
        assert order.index("park:app") < order.index("start")
        orch.nginx.point_absent.assert_called_once_with(
            orch.stack.app("app"), reload=False
        )

    def test_start_without_scaling_uses_full_stack_up(self) -> None:
        orch = self.orch
        orch.docker.running_services.side_effect = [
            [],
            RunningServices.with_apps("app"),
        ]
        self.stub_http_ready(orch.http)
        with patch.object(orch, "sync"):
            orch.start()
        orch.docker.pull_services.assert_not_called()
        orch.docker.start_stack.assert_called_once_with()

    def test_start_costops_dep_pulled_not_started(self) -> None:
        self._seed_scaling_with_api()
        orch = self._orch_cold_edge()
        with patch.object(orch, "sync"):
            orch.start()
        orch.docker.pull_services.assert_called_once_with(())
        assert set(orch.docker.build_services.call_args.args[0]) == {"api", "app"}
        started = orch.docker.start_stack.call_args.args[0]
        assert "api" not in started and "app" not in started
        store = ScalingStore(self.tmp_path)
        assert store.is_scaled_to_zero("app") and store.is_scaled_to_zero("api")

    def test_start_keeps_non_costop_dep_running(self) -> None:
        self._seed_scaling_with_sidecar()
        orch = self._orch_for_home()
        orch.docker.running_services.side_effect = [
            [],
            RunningServices.with_apps("sidecar"),
        ]
        with patch.object(orch, "sync"):
            with patch.object(orch, "_wait_app_ready") as wait:
                orch.start()
        self._assert_sidecar_started_app_deferred(orch, wait)

    def _assert_sidecar_started_app_deferred(self, orch: Orchestrator, wait) -> None:
        orch.docker.pull_services.assert_called_once_with(())
        orch.docker.build_services.assert_called_once_with(("app",))
        started = orch.docker.start_stack.call_args.args[0]
        assert "sidecar" in started and "app" not in started
        assert [c.args[0].name for c in wait.call_args_list] == ["sidecar"]
        assert ScalingStore(self.tmp_path).is_scaled_to_zero("app")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("sidecar")

    def _seed_scaling_with_api(self) -> None:
        write_applied_app(self.tmp_path, "api")
        write_applied_app(
            self.tmp_path,
            "app",
            extra={**self.scaling_extra(), "dependsOn": ["api"]},
        )

    def _seed_scaling_with_sidecar(self) -> None:
        write_applied_app(self.tmp_path, "sidecar", public_host="sidecar.test")
        write_applied_app(
            self.tmp_path,
            "app",
            extra={
                **self.scaling_extra(),
                "dependsOn": [{"name": "sidecar", "scaleWithParent": False}],
            },
        )

    def _orch_cold_edge(self) -> Orchestrator:
        orch = self._orch_for_home()
        orch.docker.running_services.side_effect = [[], RunningServices.edge()]
        return orch

    def _orch_for_home(self) -> Orchestrator:
        orch = Orchestrator(load_stack(self.tmp_path))
        orch.docker = MagicMock()
        orch.nginx = MagicMock()
        orch.http = MagicMock()
        orch.syncer = MagicMock()
        return orch
