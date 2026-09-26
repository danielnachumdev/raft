"""Unit tests for gate nginx config fingerprinting."""

from pathlib import Path

from raft.config.paths import GENERATED_DIRNAME
from raft.services.render.gate_nginx import GateNginxStamp

from ...base import RaftTestCase


class TestFingerprintGateNginx(RaftTestCase):
    def _nginx_root(self) -> Path:
        return self.tmp_path / GENERATED_DIRNAME / "nginx"

    def _stamp(self) -> GateNginxStamp:
        return GateNginxStamp(self.tmp_path)

    def test_empty_dirs_and_missing_are_stable(self) -> None:
        empty = self._stamp().fingerprint()
        assert empty == self._stamp().fingerprint()
        (self._nginx_root() / "gate-tls").mkdir(parents=True)
        assert self._stamp().fingerprint() == empty

    def test_adding_file_changes_hash(self) -> None:
        before = self._stamp().fingerprint()
        tls = self._nginx_root() / "gate-tls"
        tls.mkdir(parents=True)
        (tls / "app.conf").write_text("server {}\n", encoding="utf-8")
        after = self._stamp().fingerprint()
        assert after != before

    def test_same_bytes_unchanged(self) -> None:
        http = self._nginx_root() / "gate-http"
        http.mkdir(parents=True)
        path = http / "app.conf"
        path.write_text("listen 80;\n", encoding="utf-8")
        first = self._stamp().fingerprint()
        path.write_text("listen 80;\n", encoding="utf-8")
        assert self._stamp().fingerprint() == first

    def test_content_change_updates_hash(self) -> None:
        stream = self._nginx_root() / "gate-stream"
        stream.mkdir(parents=True)
        path = stream / "game.conf"
        path.write_text("listen 25565;\n", encoding="utf-8")
        before = self._stamp().fingerprint()
        path.write_text("listen 25566;\n", encoding="utf-8")
        assert self._stamp().fingerprint() != before

    def test_nested_directories_are_skipped(self) -> None:
        tls = self._nginx_root() / "gate-tls"
        (tls / "nested").mkdir(parents=True)
        (tls / "app.conf").write_text("server {}\n", encoding="utf-8")
        assert self._stamp().fingerprint() == self._stamp().fingerprint()

    def test_reload_stamp_roundtrip(self) -> None:
        stamp = self._stamp()
        assert stamp.read() is None
        stamp.write("abc123")
        assert stamp.read() == "abc123"

    def test_reload_stamp_empty_file_is_none(self) -> None:
        path = self.tmp_path / "state" / "gate-nginx.fingerprint"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")
        assert self._stamp().read() is None
