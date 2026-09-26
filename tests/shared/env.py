"""Isolate RAFT_* env vars so tests never touch real ~/.raft or ~/.ssh."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from raft.config import reset_logging_for_tests


@dataclass(frozen=True)
class IsolatedRaftEnv:
    """Temp data home + SSH dir + log dir with env overrides applied."""

    home: Path
    ssh_dir: Path
    log_dir: Path

    @classmethod
    def install(cls, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "IsolatedRaftEnv":
        home = tmp_path / "raft-data-home"
        home.mkdir()
        ssh_dir = tmp_path / ".ssh-raft-test"
        ssh_dir.mkdir()
        log_dir = tmp_path / "test-logs"
        log_dir.mkdir()
        monkeypatch.setenv("RAFT_DATA_HOME", str(home))
        monkeypatch.setenv("RAFT_SSH_DIR", str(ssh_dir))
        monkeypatch.setenv("RAFT_LOG_DIR", str(log_dir))
        reset_logging_for_tests()
        return cls(home=home, ssh_dir=ssh_dir, log_dir=log_dir)

    def reset_logging(self) -> None:
        reset_logging_for_tests()
