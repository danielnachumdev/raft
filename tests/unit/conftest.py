"""Isolate SSH dir, data home, and logging so tests never touch real ~/.raft or ~/.ssh."""

from pathlib import Path

import pytest

from raft.config import default_config
from tests.shared.env import IsolatedRaftEnv


@pytest.fixture(autouse=True)
def isolated_raft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env = IsolatedRaftEnv.install(tmp_path, monkeypatch)
    yield env
    env.reset_logging()


@pytest.fixture(autouse=True)
def isolated_raft_ssh_dir(isolated_raft_env: IsolatedRaftEnv) -> Path:
    return isolated_raft_env.ssh_dir


@pytest.fixture(autouse=True)
def isolated_raft_data_home(isolated_raft_env: IsolatedRaftEnv) -> Path:
    return isolated_raft_env.home


@pytest.fixture(autouse=True)
def isolated_logging(isolated_raft_env: IsolatedRaftEnv) -> Path:
    return isolated_raft_env.log_dir


@pytest.fixture(autouse=True)
def stub_cli_logging_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("raft.cli.deps.load_config", lambda *_a, **_k: default_config())
    monkeypatch.setattr(
        "raft.cli.deps.setup_logging",
        lambda *_a, **_k: tmp_path / "test-logs" / "raft.log",
    )
