"""Logging setup coverage."""

from __future__ import annotations

import logging
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import raft.config.paths as paths
from raft.config import (
    LoggingConfig,
    RaftConfig,
    default_config,
    ensure_raft_home,
    find_package_root,
    load_config,
    raft_home,
    reset_logging_for_tests,
    setup_logging,
    sync_product_templates,
)
from raft.config.settings_types import EdgeConfig
from raft.config.trace_context import TraceContext

from ...base import RaftTestCase


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

    def test_file_format_includes_tid_when_scoped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        reset_logging_for_tests()
        log_file = setup_logging(self.tmp_path, default_config())
        with TraceContext() as tid:
            logging.getLogger("raft.test").info("scoped-line")
        text = log_file.read_text(encoding="utf-8")
        assert tid in text
        assert "scoped-line" in text

    def test_file_format_uses_dash_without_scope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        reset_logging_for_tests()
        log_file = setup_logging(self.tmp_path, default_config())
        logging.getLogger("raft.test").info("no-scope-line")
        text = log_file.read_text(encoding="utf-8")
        assert " INFO - [raft.test] no-scope-line" in text

    def test_setup_prunes_oversized_existing_log(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        log_dir = self.tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "raft.log"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write_text(
            f"{stamp} INFO [raft] old-line-aaaaaaaa\n"
            f"{stamp} INFO [raft] new-line-bbbbbbbb\n",
            encoding="utf-8",
        )
        cfg = RaftConfig(
            logging=LoggingConfig(retention_max_age_days=30, retention_max_bytes=55),
            edge=EdgeConfig(),
        )
        setup_logging(self.tmp_path, cfg)
        text = log_file.read_text(encoding="utf-8")
        assert "old-line" not in text
        assert "new-line" in text
        assert log_file.stat().st_size <= 55
