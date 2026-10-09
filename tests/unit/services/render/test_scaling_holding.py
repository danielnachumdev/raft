"""Unit tests for app-owned holding page install into generated gate-http."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raft.config.settings_types import EdgeConfig
from raft.errors.cta import OperatorError
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.scaling_spec import ScalingSpec
from raft.services.render.scaling_holding import ScalingHoldingPages

from ...base import RaftTestCase, write_applied_app

_EDGE = EdgeConfig(http=80, https=443, streams=())
_PORTS = (PortSpec(name="http", container_port=80, expose="http"),)
_TIMING = {"idleSeconds": 60, "wakeTimeoutSeconds": 60, "minUpSeconds": 30}


class TestScalingHoldingPages(RaftTestCase):
    def test_prunes_stale_when_override_removed(self) -> None:
        dest = self._render_with_holding()
        assert dest.is_file()
        self._apply_scaling(_TIMING)
        self.render_applied(edge=_EDGE)
        assert not dest.is_file()

    def test_missing_checkout_errors(self) -> None:
        app = App(name="web", public_host="web.test", source="local", path="apps/web")
        spec = AppSpec(
            ports=_PORTS,
            scaling=ScalingSpec(60, 60, 30, ".raft/holding.html"),
        )
        with pytest.raises(OperatorError, match="checkout missing"):
            ScalingHoldingPages().install(self.tmp_path, [app], {"web": spec})

    def test_symlink_escape_errors(self) -> None:
        app_root = self.tmp_path / "apps" / "web"
        app_root.mkdir(parents=True)
        outside = self.tmp_path / "outside.html"
        outside.write_text("<html>nope</html>", encoding="utf-8")
        link = app_root / "hold.html"
        link.symlink_to(outside)
        app = App(name="web", public_host="web.test", source="local", path="apps/web")
        spec = AppSpec(ports=_PORTS, scaling=ScalingSpec(60, 60, 30, "hold.html"))
        with pytest.raises(OperatorError, match="escapes"):
            ScalingHoldingPages().install(self.tmp_path, [app], {"web": spec})

    def _render_with_holding(self) -> Path:
        self._apply_scaling({**_TIMING, "holdingPage": ".raft/holding.html"})
        page = self.tmp_path / "apps" / "web" / ".raft" / "holding.html"
        page.parent.mkdir(parents=True)
        page.write_text("<html>demo-api</html>", encoding="utf-8")
        self.render_applied(edge=_EDGE)
        return self.tmp_path / "generated/nginx/gate-http/holding/web.html"

    def _apply_scaling(self, scaling: dict[str, Any]) -> None:
        write_applied_app(
            self.tmp_path, "web", public_host="web.test", extra={"scaling": scaling}
        )
