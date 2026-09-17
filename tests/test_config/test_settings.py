"""settings.yaml config loading and logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import raft.config.paths as paths
from raft.config import (
    LoggingConfig,
    default_config,
    ensure_raft_home,
    find_package_root,
    load_config,
    raft_home,
    reset_logging_for_tests,
    setup_logging,
    sync_product_templates,
)

from ..base import RaftTestCase


class TestConfig(RaftTestCase):
    def test_default_config(self) -> None:
        cfg = default_config()
        assert cfg.logging.dir == "logs"
        assert cfg.logging.file == "raft.log"
        assert cfg.logging.level == "INFO"

    def test_load_missing_uses_defaults(self) -> None:
        settings = self.tmp_path / "settings.yaml"
        if settings.is_file():
            settings.unlink()
        assert load_config(self.tmp_path) == default_config()

    def test_load_from_file(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            """
logging:
  dir: var/log
  file: orch.log
  level: DEBUG
""",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.logging.dir == "var/log"
        assert cfg.logging.file == "orch.log"
        assert cfg.logging.level == "DEBUG"

    def test_rejects_bad_logging_table(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("logging: nope\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="must be a mapping"):
            load_config(self.tmp_path)

    def test_load_logging_null(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("# no logging mapping\n", encoding="utf-8")
        assert load_config(self.tmp_path).logging.dir == "logs"

    def test_resolve_dir_relative_absolute_and_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        cfg = LoggingConfig(dir="logs")
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "logs").resolve()
        abs_cfg = LoggingConfig(dir=str(self.tmp_path / "abs-logs"))
        assert abs_cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "abs-logs").resolve()
        monkeypatch.setenv("RAFT_LOG_DIR", str(self.tmp_path / "env-logs"))
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "env-logs").resolve()


class TestRaftHome(RaftTestCase):
    def test_raft_home_env_and_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_DATA_HOME", str(self.tmp_path / "custom"))
        assert raft_home() == (self.tmp_path / "custom").resolve()
        monkeypatch.delenv("RAFT_DATA_HOME", raising=False)
        assert raft_home() == (Path.home() / ".raft").resolve()

    def test_ensure_syncs_templates(self) -> None:
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        assert (home / "compose.yaml").is_file()
        assert (home / "nginx" / "gate" / "nginx.conf").is_file()
        assert (home / "generated" / "compose.apps.yaml").is_file()
        assert (home / "generated" / "compose.edge.yaml").is_file()
        assert (home / "state" / "apps").is_dir()
        ensure_raft_home(home)
        assert (home / "nginx" / "gate" / "nginx.conf").is_file()

    def test_gate_nginx_conf_uses_builtin_stream(self) -> None:
        """nginx:alpine builds stream in; load_module ngx_stream_module.so crashes gate."""
        home = self.tmp_path / "home"
        ensure_raft_home(home)
        conf = (home / "nginx" / "gate" / "nginx.conf").read_text(encoding="utf-8")
        assert "load_module" not in conf
        assert "stream {" in conf
        assert "include /etc/nginx/stream-generated/*.conf;" in conf

    def test_load_edge_section(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            """
logging:
  level: INFO
edge:
  http: 8080
  https: null
  streams:
    - name: smtp
      port: 25
      protocol: tcp
""",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.edge.http == 8080
        assert cfg.edge.https is None
        assert len(cfg.edge.streams) == 1
        assert cfg.edge.streams[0].name == "smtp"
        assert cfg.edge.published_ports() == [(8080, "tcp"), (25, "tcp")]

    def test_edge_rejects_duplicate_stream_port(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            """
edge:
  streams:
    - name: a
      port: 25
    - name: b
      port: 25
""",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="duplicate port"):
            load_config(self.tmp_path)

    def test_find_package_root_bundled(self) -> None:
        root = find_package_root()
        assert (root / "compose.yaml").is_file()
        assert (root / "nginx").is_dir()

    def test_sync_missing_file_template(self) -> None:
        empty = self.tmp_path / "empty-pkg"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="missing package template"):
            sync_product_templates(self.tmp_path / "dest", empty)

    def test_sync_missing_dir_template(self) -> None:
        pkg = self.tmp_path / "partial-pkg"
        pkg.mkdir()
        (pkg / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        dest = self.tmp_path / "dest"
        dest.mkdir()
        with pytest.raises(FileNotFoundError, match="missing package template dir"):
            sync_product_templates(dest, pkg)

    def test_find_package_root_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(paths, "_bundled_share", lambda: self.tmp_path / "nope")
        orphan = self.tmp_path / "orphan"
        orphan.mkdir()
        with pytest.raises(RuntimeError, match="package templates"):
            find_package_root(orphan)


class TestSetupLogging(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _reset_logging(self, _raft_base) -> None:
        reset_logging_for_tests()
        yield
        reset_logging_for_tests()

    def test_writes_file_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        reset_logging_for_tests()
        log_file = setup_logging(self.tmp_path, default_config())
        assert log_file == self.tmp_path / "logs" / "raft.log"
        assert log_file.parent.is_dir()
        root = logging.getLogger("raft")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.FileHandler)
        assert root.propagate is False
        logging.getLogger("raft.test").info("hello-file")
        assert "hello-file" in log_file.read_text(encoding="utf-8")
