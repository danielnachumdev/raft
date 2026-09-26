"""Logging setup coverage."""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError
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
