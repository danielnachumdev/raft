"""Unit tests for router nginx config fingerprinting."""

from pathlib import Path

from raft.core.core.config.paths import GENERATED_DIRNAME
from raft.core.lifecycle.render.router_nginx import RouterNginxStamp

from tests.unit.base import RaftTestCase


class TestFingerprintRouterNginx(RaftTestCase):
    def _nginx_root(self) -> Path:
        return self.tmp_path / GENERATED_DIRNAME / "nginx"

    def _stamp(self) -> RouterNginxStamp:
        return RouterNginxStamp(self.tmp_path)

    def test_empty_dirs_and_missing_are_stable(self) -> None:
        empty = self._stamp().fingerprint()
        assert empty == self._stamp().fingerprint()
        (self._nginx_root() / "upstreams").mkdir(parents=True, exist_ok=True)
        assert self._stamp().fingerprint() == empty

    def test_hosts_conf_changes_hash(self) -> None:
        before = self._stamp().fingerprint()
        router = self._nginx_root() / "router"
        router.mkdir(parents=True, exist_ok=True)
        (router / "hosts.conf").write_text("server {}\n", encoding="utf-8")
        assert self._stamp().fingerprint() != before

    def test_upstream_file_changes_hash(self) -> None:
        ups = self._nginx_root() / "upstreams"
        ups.mkdir(parents=True, exist_ok=True)
        path = ups / "app-http.conf"
        path.write_text("upstream app {}\n", encoding="utf-8")
        before = self._stamp().fingerprint()
        path.write_text("upstream app { server x; }\n", encoding="utf-8")
        assert self._stamp().fingerprint() != before

    def test_nested_upstream_dirs_are_skipped(self) -> None:
        ups = self._nginx_root() / "upstreams"
        (ups / "nested").mkdir(parents=True, exist_ok=True)
        (ups / "app-http.conf").write_text("upstream app {}\n", encoding="utf-8")
        assert self._stamp().fingerprint() == self._stamp().fingerprint()

    def test_reload_stamp_roundtrip(self) -> None:
        stamp = self._stamp()
        assert stamp.read() is None
        stamp.write("abc123")
        assert stamp.read() == "abc123"

    def test_reload_stamp_empty_file_is_none(self) -> None:
        path = self.tmp_path / "state" / "router-nginx.fingerprint"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")
        assert self._stamp().read() is None
