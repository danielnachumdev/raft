"""Unit coverage for UpDepends helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.actions.up_depends import UpDepends

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory, StackMakers


class TestUpDepends(RaftTestCase):
    def _helper(self, apps=None) -> UpDepends:
        stack = StackMakers.make_stack(
            self.tmp_path, apps or (AppMakers.make_app("demo-api"),)
        )
        return UpDepends(stack, MagicMock())

    def test_up_dep_unknown_app(self) -> None:
        helper = self._helper()
        with pytest.raises(OperatorError, match="not in applied apps"):
            helper.up_dep("missing")

    def test_restore_upstreams_skips_unknown_names(self) -> None:
        helper = self._helper()
        with patch(
            "raft.core.observe.ops.actions.up_depends.NginxUpstreams"
        ) as nginx_cls:
            nginx = MagicMock()
            nginx_cls.return_value = nginx
            helper.restore_upstreams(("demo-api", "ghost"))
        nginx.point_steady.assert_called_once()
        assert nginx.point_steady.call_args.args[0].name == "demo-api"

    def test_edges_for_bad_yaml_returns_empty(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "demo-api")
        path = self.tmp_path / "services" / "demo-api" / "app.yaml"
        path.write_text("not: valid: app: yaml\n", encoding="utf-8")
        helper = self._helper()
        assert helper._edges_for("demo-api") == ()

    def test_edges_for_missing_file(self) -> None:
        helper = self._helper()
        assert helper._edges_for("demo-api") == ()
