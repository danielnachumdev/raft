"""Isolate SSH dir, data home, and logging so tests never touch real ~/.raft or ~/.ssh."""

from pathlib import Path

import pytest

from raft.core.core.config import RaftConfig
from raft.services.cli.utils.deps import lazy
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

    class _StubHostLogging:
        def configure(self, *_a, **_k):
            return tmp_path / "test-logs" / "raft.log"

    real_call = lazy.call

    def call(name: str, *args, **kwargs):
        if name == "SettingsLoader":
            return _StubSettingsLoader()
        if name == "HostLogging":
            return _StubHostLogging()
        return real_call(name, *args, **kwargs)

    monkeypatch.setattr(lazy, "call", call)
