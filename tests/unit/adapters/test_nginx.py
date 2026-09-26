"""Nginx upstream file management (app + port name)."""

from unittest.mock import MagicMock

import pytest

from raft.adapters import NginxUpstreams
from raft.models.ports import PortSpec

from tests.shared.nginx import UpstreamFile

from .base import AdapterTestCase


class TestNginxUpstreams(AdapterTestCase):
    def test_ensure_steady_file_creates_and_skips(self) -> None:
        nginx = NginxUpstreams(self.stack, MagicMock())
        nginx.ensure_steady_file(self.app)
        port = PortSpec(name="http", container_port=80, expose="http")
        path = self.stack.upstream_file(self.app, port)
        assert path.is_file()
        assert path.name == "app-http.conf"
        UpstreamFile.assert_contains(path, "upstream app_http", "server app:80")
        text = path.read_text(encoding="utf-8")
        nginx.ensure_steady_file(self.app)
        assert path.read_text(encoding="utf-8") == text

    def test_point_at_ok_and_fail(self) -> None:
        self.stack.upstreams_dir.mkdir(parents=True)
        docker = MagicMock()
        docker.router_sees_upstream_target.return_value = True
        nginx = NginxUpstreams(self.stack, docker)
        nginx.point_at(self.app, "app_tmp")
        port = PortSpec(name="http", container_port=80, expose="http")
        UpstreamFile.assert_contains(
            self.stack.upstream_file(self.app, port), "server app_tmp:80"
        )
        docker.router_sees_upstream_target.return_value = False
        with pytest.raises(RuntimeError, match="does not see upstream target"):
            nginx.point_at(self.app, "missing")
