"""Isolate SSH dir, data home, and logging so tests never touch real ~/.raft or ~/.ssh."""

from pathlib import Path

import pytest

from raft.config import RaftConfig
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
    class _StubSettingsLoader:
        def load(self, *_a, **_k):
            return RaftConfig()

    monkeypatch.setattr(
        "raft.cli.commands.raft_commands.SettingsLoader",
        _StubSettingsLoader,
    )

    class _StubHostLogging:
        def configure(self, *_a, **_k):
            return tmp_path / "test-logs" / "raft.log"

    monkeypatch.setattr(
        "raft.cli.commands.raft_commands.HostLogging",
        _StubHostLogging,
    )
