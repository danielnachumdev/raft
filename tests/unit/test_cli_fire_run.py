"""Unit tests for fail-fast Fire unused-arg rejection."""

from __future__ import annotations

import fire
from fire import core as fire_core

from raft.cli.fire_run import _ORIGINAL_CALL, run_fire


class _Leaf:
    def status(self, live: bool = False) -> str:
        return "ran"

    def __call__(self, live: bool = False) -> str:
        return "called"


def test_run_fire_rejects_unknown_flag_before_routine() -> None:
    calls: list[str] = []

    class CLI:
        def status(self, live: bool = False) -> None:
            calls.append("status")

    try:
        run_fire(CLI, command=["status", "--leiv"], name="raft")
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")

    assert calls == []
    assert fire_core._CallAndUpdateTrace is _ORIGINAL_CALL


def test_run_fire_allows_valid_flags() -> None:
    calls: list[bool] = []

    class CLI:
        def status(self, live: bool = False) -> None:
            calls.append(live)

    assert run_fire(CLI, command=["status", "--live"], name="raft") is None
    assert calls == [True]


def test_run_fire_rejects_unused_on_callable_object() -> None:
    """Callable treatment path (not used by RaftCLI, but covered for fail-fast)."""
    leaf = _Leaf()
    try:
        run_fire({"go": leaf}, command=["go", "--leiv"], name="raft")
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_run_fire_restores_hook_after_success() -> None:
    run_fire(_Leaf, command=["status"], name="raft")
    assert fire_core._CallAndUpdateTrace is _ORIGINAL_CALL
    # Stock Fire still runs-then-rejects without our hook.
    try:
        fire.Fire(_Leaf, command=["status", "--leiv"], name="raft")
    except SystemExit:
        pass
    assert fire_core._CallAndUpdateTrace is _ORIGINAL_CALL
