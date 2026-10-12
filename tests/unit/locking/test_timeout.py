"""Lock timeout resolution coverage."""

import pytest

from raft.errors.cta import OperatorError
from raft.locking import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    ENV_LOCK_TIMEOUT,
    LockTimeout,
)


class TestResolveLockTimeout:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_LOCK_TIMEOUT, raising=False)
        assert LockTimeout.resolve() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_override_arg(self) -> None:
        assert LockTimeout.resolve(1.5) == 1.5

    def test_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "12")
        assert LockTimeout.resolve() == 12.0

    def test_invalid_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "nope")
        with pytest.raises(OperatorError, match="RAFT_LOCK_TIMEOUT_SECONDS"):
            LockTimeout.resolve()

    def test_blank_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "  ")
        assert LockTimeout.resolve() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_negative_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "-5")
        with pytest.raises(OperatorError, match="non-negative"):
            LockTimeout.resolve()

    def test_negative(self) -> None:
        with pytest.raises(OperatorError, match="non-negative"):
            LockTimeout.resolve(-1)
