"""Healer dependsOn chain coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer
from raft.errors.cta import OperatorError
from raft.models.state.scaling_store import ScalingStore

from ..base import write_applied_app
from .base import ControllerTestCase


class TestHealerDependsOn(ControllerTestCase):
    def test_restart_starts_stopped_dep(self, tmp_path: Path) -> None:
        _home, docker, healer = self._dep_healer(
            tmp_path, api_status="restarting", api_health="none"
        )
        with self.with_heal_locks():
            healer.tick(now=1.0)
        assert [c.args[0] for c in docker.start_service.call_args_list] == [
            "api",
            self.APP,
        ]

    def test_restart_skips_running_dep(self, tmp_path: Path) -> None:
        _home, docker, healer = self._dep_healer(
            tmp_path, api_status="running", api_health="healthy"
        )
        with self.with_heal_locks():
            healer.tick(now=1.0)
        docker.start_service.assert_called_once_with(self.APP)

    def test_defer_when_dep_scaled_to_zero(self, tmp_path: Path) -> None:
        home, docker, healer = self._dep_healer(
            tmp_path, api_status="exited", api_health="none"
        )
        ScalingStore(home).mark_scaled_to_zero("api")
        with self.with_heal_locks():
            healer.tick(now=1.0)
        docker.start_service.assert_not_called()
        assert healer.restart_counts.get(self.APP, 0) == 0

    def test_depends_on_error_blocks_restart(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, self.APP, extra={"dependsOn": ["missing"]})
        docker = MagicMock()
        docker.service_runtime.return_value = ("exited", "none")
        cfg = HealingConfig(enabled=True, fail_threshold=1, cooldown_seconds=0)
        with self.with_heal_locks():
            Healer(home, cfg, docker).tick(now=1.0)
        docker.start_service.assert_not_called()

    def test_start_dep_operator_error(self, tmp_path: Path) -> None:
        _home, docker, healer = self._dep_healer(
            tmp_path, api_status="restarting", api_health="none"
        )
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        with self.with_heal_locks():
            healer.tick(now=1.0)
        assert healer.restart_counts.get(self.APP, 0) == 0

    def test_edges_for_missing_and_bad(self, tmp_path: Path) -> None:
        healer = Healer(self.raft_home(tmp_path), HealingConfig(enabled=True), MagicMock())
        assert healer._deps.edges_for(tmp_path / "nope.yaml", "x") == ()
        bad = tmp_path / "bad.yaml"
        bad.write_text("not: yaml: [[", encoding="utf-8")
        assert healer._deps.edges_for(bad, "x") == ()

    def test_ensure_dep_missing_compose(self, tmp_path: Path) -> None:
        _home, docker, healer = self._dep_healer(
            tmp_path, api_status="running", api_health="healthy"
        )
        with patch.object(healer._deps, "compose_id", return_value=None):
            with self.with_heal_locks():
                healer.tick(now=1.0)
        docker.start_service.assert_not_called()

    def test_escalate_defers_on_scaled_dep(self, tmp_path: Path) -> None:
        home, _docker, healer = self._dep_healer(
            tmp_path, api_status="running", api_health="healthy"
        )
        ScalingStore(home).mark_scaled_to_zero("api")
        healer.restart_counts[self.APP] = 5
        deploy = MagicMock()
        healer.deploy = deploy
        with self.with_heal_locks():
            healer.tick(now=1.0)
        deploy.assert_not_called()

    def test_compose_id_unknown(self, tmp_path: Path) -> None:
        healer = Healer(self.applied_home(tmp_path), HealingConfig(enabled=True), MagicMock())
        assert healer._deps.compose_id("ghost") is None

    def _dep_healer(self, tmp_path: Path, *, api_status: str, api_health: str):
        home = self.raft_home(tmp_path)
        write_applied_app(home, "api")
        write_applied_app(home, self.APP, extra={"dependsOn": ["api"]})
        docker = MagicMock()
        docker.service_runtime.side_effect = lambda sid: (
            (api_status, api_health) if sid == "api" else ("exited", "none")
        )
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        return home, docker, Healer(home, cfg, docker)
