"""Unit tests for ``raft logs`` name resolution."""

from __future__ import annotations

import pytest

from raft.errors import OperatorError
from raft.models import CONTROLLER_COMPOSE_ID, GATE_COMPOSE_ID, ROUTER_COMPOSE_ID
from raft.services.ops.logs.targets import LogsTargets

from ....base import RaftTestCase, make_app, make_stack


class TestLogsTargets(RaftTestCase):
    def test_edge_aliases_and_compose_ids(self) -> None:
        targets = LogsTargets(make_stack(self.tmp_path, ()))
        assert targets.resolve("gate") == (GATE_COMPOSE_ID,)
        assert targets.resolve("raft-gate") == (GATE_COMPOSE_ID,)
        assert targets.resolve("router", "controller") == (
            ROUTER_COMPOSE_ID,
            CONTROLLER_COMPOSE_ID,
        )

    def test_app_name_and_compose_id(self) -> None:
        app = make_app("web", group="demo")
        targets = LogsTargets(make_stack(self.tmp_path, (app,)))
        assert targets.resolve("web") == ("demo-web",)
        assert targets.resolve("demo-web") == ("demo-web",)

    def test_empty_resolves_all_core_services(self) -> None:
        app = make_app("app")
        stack = make_stack(self.tmp_path, (app,))
        assert LogsTargets(stack).resolve() == stack.core_services

    def test_unknown_raises_with_fix(self) -> None:
        targets = LogsTargets(make_stack(self.tmp_path, (make_app("app"),)))
        with pytest.raises(OperatorError, match="unknown logs target") as exc:
            targets.resolve("nope")
        assert "Fix:" in str(exc.value)
        assert "app" in str(exc.value)
