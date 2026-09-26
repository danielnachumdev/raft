"""Integration isolation — temp raft home, no Docker."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.shared.env import IsolatedRaftEnv


@pytest.fixture(autouse=True)
def isolated_raft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    env = IsolatedRaftEnv.install(tmp_path, monkeypatch)
    yield env.home
    env.reset_logging()
