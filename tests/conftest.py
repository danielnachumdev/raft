"""Isolate SSH dir, data home, and logging so tests never touch real ~/.raft or ~/.ssh."""

from pathlib import Path

import pytest

from raft.config import default_config, reset_logging_for_tests


@pytest.fixture(autouse=True)
def isolated_raft_ssh_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ssh = tmp_path / ".ssh-raft-test"
    ssh.mkdir()
    monkeypatch.setenv("RAFT_SSH_DIR", str(ssh))
    return ssh


@pytest.fixture(autouse=True)
def isolated_raft_data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "raft-data-home"
    home.mkdir()
    monkeypatch.setenv("RAFT_DATA_HOME", str(home))
    return home


@pytest.fixture(autouse=True)
def isolated_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log_dir = tmp_path / "test-logs"
    log_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("RAFT_LOG_DIR", str(log_dir))
    reset_logging_for_tests()
    yield log_dir
    reset_logging_for_tests()

@pytest.fixture(autouse=True)
def stub_cli_logging_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("raft.cli.deps.load_config", lambda *_a, **_k: default_config())
    monkeypatch.setattr(
        "raft.cli.deps.setup_logging",
        lambda *_a, **_k: tmp_path / "test-logs" / "raft.log",
    )
