"""Unit tests for ``raft logs`` name resolution."""

from __future__ import annotations

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import (
    CONTROLLER_COMPOSE_ID,
    DASHBOARD_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
)
from raft.core.observe.ops.logs.targets import LogsTargets

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
        assert targets.resolve("dashboard") == (DASHBOARD_COMPOSE_ID,)
        assert targets.resolve("raft-dashboard") == (DASHBOARD_COMPOSE_ID,)

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

    def test_known_labels_include_dashboard_when_enabled(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "dashboard: {enabled: true}\n", encoding="utf-8"
        )
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("app"),))
        labels = LogsTargets(stack).known_labels()
        assert "dashboard" in labels
        assert "app" in labels

    def test_known_labels_omit_dashboard_when_disabled(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("app"),))
        assert "dashboard" not in LogsTargets(stack).known_labels()
