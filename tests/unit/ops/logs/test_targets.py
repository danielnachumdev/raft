"""Unit tests for ``raft logs`` name resolution."""

from __future__ import annotations

import pytest

from raft.errors.cta import OperatorError
from raft.models.app import CONTROLLER_COMPOSE_ID, GATE_COMPOSE_ID, ROUTER_COMPOSE_ID
from raft.ops.logs.targets import LogsTargets

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestLogsTargets(RaftTestCase):
    def test_edge_aliases_and_compose_ids(self) -> None:
        targets = LogsTargets(StackMakers.make_stack(self.tmp_path, ()))
        assert targets.resolve("gate") == (GATE_COMPOSE_ID,)
        assert targets.resolve("raft-gate") == (GATE_COMPOSE_ID,)
        assert targets.resolve("router", "controller") == (
            ROUTER_COMPOSE_ID,
            CONTROLLER_COMPOSE_ID,
        )

    def test_app_name_and_compose_id(self) -> None:
        app = AppMakers.make_app("web", group="demo")
        targets = LogsTargets(StackMakers.make_stack(self.tmp_path, (app,)))
        assert targets.resolve("web") == ("demo-web",)
        assert targets.resolve("demo-web") == ("demo-web",)

    def test_empty_resolves_all_core_services(self) -> None:
        app = AppMakers.make_app("app")
        stack = StackMakers.make_stack(self.tmp_path, (app,))
        assert LogsTargets(stack).resolve() == stack.core_services

    def test_unknown_raises_with_fix(self) -> None:
        targets = LogsTargets(StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("app"),)))
        with pytest.raises(OperatorError, match="unknown logs target") as exc:
            targets.resolve("nope")
        assert "Fix:" in str(exc.value)
        assert "app" in str(exc.value)
