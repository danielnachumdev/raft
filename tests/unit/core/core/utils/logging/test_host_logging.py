"""Host logging setup coverage."""

import logging
from datetime import datetime
from pathlib import Path

import pytest

from raft.core.core.config import LoggingConfig, RaftConfig
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.utils import HostLogging, LogRotatingFileHandler, TraceContext
from tests.shared.logging_reset import LoggingReset


class TestHostLogging:
    @pytest.fixture(autouse=True)
    def _reset_logging(self) -> None:
        LoggingReset().for_tests()
        yield
        LoggingReset().for_tests()

    def test_writes_file_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        LoggingReset().for_tests()
        log_file = HostLogging().configure(tmp_path, RaftConfig())
        assert log_file == tmp_path / "logs" / "raft.log"
        assert log_file.parent.is_dir()
        root = logging.getLogger("raft")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], LogRotatingFileHandler)
        assert root.propagate is False
        logging.getLogger("raft.test").info("hello-file")
        assert "hello-file" in log_file.read_text(encoding="utf-8")

    def test_file_format_includes_tid_when_scoped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        LoggingReset().for_tests()
        log_file = HostLogging().configure(tmp_path, RaftConfig())
        with TraceContext() as tid:
            logging.getLogger("raft.test").info("scoped-line")
        text = log_file.read_text(encoding="utf-8")
        assert tid in text
        assert "scoped-line" in text

    def test_file_format_uses_dash_without_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        LoggingReset().for_tests()
        log_file = HostLogging().configure(tmp_path, RaftConfig())
        logging.getLogger("raft.test").info("no-scope-line")
        text = log_file.read_text(encoding="utf-8")
        assert " INFO - [raft.test] no-scope-line" in text

    def test_setup_seals_oversized_existing_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "raft.log"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = (
            f"{stamp} INFO [raft] old-line-aaaaaaaa\n"
            f"{stamp} INFO [raft] new-line-bbbbbbbb\n"
        )
        log_file.write_text(payload, encoding="utf-8")
        cfg = RaftConfig(
            logging=LoggingConfig(retention_max_age_days=30, retention_max_bytes=55),
            edge=EdgeConfig(),
        )
        HostLogging().configure(tmp_path, cfg)
        day = datetime.now().strftime("%Y-%m-%d")
        sealed = log_dir / f"raft.log.{day}"
        assert sealed.read_text(encoding="utf-8") == payload
