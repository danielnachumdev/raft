"""Lock timeout resolution coverage."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.errors import OperatorError
from raft.models.ports import PortSpec
from raft.services.deploy.locking import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    ENV_LOCK_TIMEOUT,
    app_and_stack_locks,
    app_deploy_lock,
    app_lock_path,
    exclusive_lock,
    resolve_lock_timeout,
    stack_lock,
    stack_lock_path,
)
from raft.services.deploy.orchestrator import Orchestrator
from raft.services.render import StackRenderer

from ...base import RaftTestCase, make_local_stack, write_applied_app

class TestResolveLockTimeout:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_LOCK_TIMEOUT, raising=False)
        assert resolve_lock_timeout() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_override_arg(self) -> None:
        assert resolve_lock_timeout(1.5) == 1.5

    def test_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "12")
        assert resolve_lock_timeout() == 12.0

    def test_invalid_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "nope")
        with pytest.raises(OperatorError, match="RAFT_LOCK_TIMEOUT_SECONDS"):
            resolve_lock_timeout()

    def test_blank_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "  ")
        assert resolve_lock_timeout() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_negative_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "-5")
        with pytest.raises(OperatorError, match="non-negative"):
            resolve_lock_timeout()

    def test_negative(self) -> None:
        with pytest.raises(OperatorError, match="non-negative"):
            resolve_lock_timeout(-1)


