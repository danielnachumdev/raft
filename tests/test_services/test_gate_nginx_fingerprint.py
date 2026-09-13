"""Unit tests for gate nginx config fingerprinting."""

from pathlib import Path

from raft.config.paths import GENERATED_DIRNAME
from raft.services.render import (
    fingerprint_gate_nginx,
    read_gate_nginx_reload_stamp,
    write_gate_nginx_reload_stamp,
)

from ..base import RaftTestCase


class TestFingerprintGateNginx(RaftTestCase):
    def _nginx_root(self) -> Path:
        return self.tmp_path / GENERATED_DIRNAME / "nginx"

    def test_empty_dirs_and_missing_are_stable(self) -> None:
        empty = fingerprint_gate_nginx(self.tmp_path)
        assert empty == fingerprint_gate_nginx(self.tmp_path)
        (self._nginx_root() / "gate-tls").mkdir(parents=True)
        assert fingerprint_gate_nginx(self.tmp_path) == empty

    def test_adding_file_changes_hash(self) -> None:
        before = fingerprint_gate_nginx(self.tmp_path)
        tls = self._nginx_root() / "gate-tls"
        tls.mkdir(parents=True)
        (tls / "playcrate.conf").write_text("server {}\n", encoding="utf-8")
        after = fingerprint_gate_nginx(self.tmp_path)
        assert after != before

    def test_same_bytes_unchanged(self) -> None:
        http = self._nginx_root() / "gate-http"
        http.mkdir(parents=True)
        path = http / "app.conf"
        path.write_text("listen 80;\n", encoding="utf-8")
        first = fingerprint_gate_nginx(self.tmp_path)
        path.write_text("listen 80;\n", encoding="utf-8")
        assert fingerprint_gate_nginx(self.tmp_path) == first

    def test_content_change_updates_hash(self) -> None:
        stream = self._nginx_root() / "gate-stream"
        stream.mkdir(parents=True)
        path = stream / "game.conf"
        path.write_text("listen 25565;\n", encoding="utf-8")
        before = fingerprint_gate_nginx(self.tmp_path)
        path.write_text("listen 25566;\n", encoding="utf-8")
        assert fingerprint_gate_nginx(self.tmp_path) != before

    def test_nested_directories_are_skipped(self) -> None:
        tls = self._nginx_root() / "gate-tls"
        (tls / "nested").mkdir(parents=True)
        (tls / "app.conf").write_text("server {}\n", encoding="utf-8")
        assert fingerprint_gate_nginx(self.tmp_path) == fingerprint_gate_nginx(self.tmp_path)

    def test_reload_stamp_roundtrip(self) -> None:
        assert read_gate_nginx_reload_stamp(self.tmp_path) is None
        write_gate_nginx_reload_stamp(self.tmp_path, "abc123")
        assert read_gate_nginx_reload_stamp(self.tmp_path) == "abc123"

    def test_reload_stamp_empty_file_is_none(self) -> None:
        path = self.tmp_path / "state" / "gate-nginx.fingerprint"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")
        assert read_gate_nginx_reload_stamp(self.tmp_path) is None
