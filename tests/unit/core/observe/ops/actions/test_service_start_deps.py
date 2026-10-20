"""ServiceActions.start brings up dependsOn (wake order) unless --no-deps."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.ops.actions import ServiceActions

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory, StackMakers

_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 30,
    "minUpSeconds": 15,
}


class TestServiceActionsStartDeps(RaftTestCase):
    def _seed_fe_be(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", extra={"scaling": _SCALING}
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "frontend",
            extra={"dependsOn": ["demo-api"]},
        )

    def _actions(self) -> tuple[ServiceActions, MagicMock]:
        apps = (AppMakers.make_app("demo-api"), AppMakers.make_app("frontend"))
        stack = StackMakers.make_stack(self.tmp_path, apps)
        docker = MagicMock()
        return ServiceActions(stack, docker=docker), docker

    def _with_chain_locks(self):
        return patch("raft.core.observe.ops.actions.service.AppsAndStackLocks")

    def _with_app_locks(self):
        return patch("raft.core.observe.ops.actions.service.AppAndStackLocks")

    @staticmethod
    def _enter(mock_cm) -> None:
        mock_cm.return_value.__enter__ = MagicMock()
        mock_cm.return_value.__exit__ = MagicMock(return_value=False)

    def test_start_starts_depends_on_first(self) -> None:
        self._seed_fe_be()
        actions, docker = self._actions()
        with self._with_chain_locks() as locks:
            self._enter(locks)
            with patch(
                "raft.core.observe.ops.actions.start_depends.NginxUpstreams"
            ) as nginx_cls:
                nginx = MagicMock()
                nginx_cls.return_value = nginx
                result = actions.start("frontend")
        assert docker.start_service.call_args_list == [
            call("demo-api"),
            call("frontend"),
        ]
        assert result["started_deps"] == ["demo-api"]
        assert result["no_deps"] is False
        locks.assert_called_once()
        assert set(locks.call_args.args[1]) == {"demo-api", "frontend"}
        nginx.point_steady.assert_called()

    def test_start_no_deps_skips_depends_on(self) -> None:
        self._seed_fe_be()
        actions, docker = self._actions()
        with self._with_app_locks() as locks:
            self._enter(locks)
            result = actions.start("frontend", no_deps=True)
        docker.start_service.assert_called_once_with("frontend")
        assert result["started_deps"] == []
        assert result["no_deps"] is True

    def test_start_clears_scaled_dep(self) -> None:
        self._seed_fe_be()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("demo-api")
        actions, docker = self._actions()
        with self._with_chain_locks() as locks:
            self._enter(locks)
            with patch("raft.core.observe.ops.actions.start_depends.NginxUpstreams"):
                actions.start("frontend")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("demo-api")
        assert docker.start_service.call_args_list[0] == call("demo-api")

    def test_start_missing_dep_raises(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "frontend",
            extra={"dependsOn": ["missing-backend"]},
        )
        apps = (AppMakers.make_app("frontend"),)
        stack = StackMakers.make_stack(self.tmp_path, apps)
        actions = ServiceActions(stack, docker=MagicMock())
        with pytest.raises(OperatorError, match="dependsOn"):
            actions.start("frontend")
