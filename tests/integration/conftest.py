"""Integration isolation — temp raft home, no Docker."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.config import reset_logging_for_tests


@pytest.fixture(autouse=True)
def isolated_raft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "raft-data-home"
    home.mkdir()
    ssh = tmp_path / ".ssh-raft-test"
    ssh.mkdir()
    log_dir = tmp_path / "test-logs"
    log_dir.mkdir()
    monkeypatch.setenv("RAFT_DATA_HOME", str(home))
    monkeypatch.setenv("RAFT_SSH_DIR", str(ssh))
    monkeypatch.setenv("RAFT_LOG_DIR", str(log_dir))
    reset_logging_for_tests()
    yield home
    reset_logging_for_tests()
