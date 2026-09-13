"""raft.yaml config loading and logging setup."""

import logging

import pytest

from ..base import RaftTestCase
from raft.config import (
    LoggingConfig,
    default_config,
    load_config,
    reset_logging_for_tests,
    setup_logging,
)


class TestConfig(RaftTestCase):
    def test_default_config(self) -> None:
        cfg = default_config()
        assert cfg.logging.dir == "logs"
        assert cfg.logging.file == "raft.log"
        assert cfg.logging.level == "INFO"

    def test_load_missing_uses_defaults(self) -> None:
        (self.tmp_path / "raft.yaml").unlink()
        assert load_config(self.tmp_path) == default_config()

    def test_load_from_file(self) -> None:
        (self.tmp_path / "raft.yaml").write_text(
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
        (self.tmp_path / "raft.yaml").write_text("logging: nope\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a mapping"):
            load_config(self.tmp_path)

    def test_load_logging_null(self) -> None:
        (self.tmp_path / "raft.yaml").write_text("# no logging mapping\n", encoding="utf-8")
        assert load_config(self.tmp_path).logging.dir == "logs"

    def test_resolve_dir_relative_absolute_and_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        cfg = LoggingConfig(dir="logs")
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "logs").resolve()
        abs_cfg = LoggingConfig(dir=str(self.tmp_path / "abs-logs"))
        assert abs_cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "abs-logs").resolve()
        monkeypatch.setenv("RAFT_LOG_DIR", str(self.tmp_path / "env-logs"))
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "env-logs").resolve()


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
