"""Unit tests for fail-fast Fire unused-arg rejection."""

from __future__ import annotations

import fire
from fire import core as fire_core

from raft.cli.utils.fire_run import FireRunner


class _Leaf:
    def status(self, live: bool = False) -> str:
        return "ran"

    def __call__(self, live: bool = False) -> str:
        return "called"


def _stock_call():
    return fire_core._CallAndUpdateTrace


def test_run_fire_rejects_unknown_flag_before_routine() -> None:
    calls: list[str] = []
    before = _stock_call()

    class CLI:
        def status(self, live: bool = False) -> None:
            calls.append("status")

    try:
        FireRunner().run(CLI, command=["status", "--leiv"], name="raft")
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")

    assert calls == []
    assert fire_core._CallAndUpdateTrace is before


def test_run_fire_allows_valid_flags() -> None:
    calls: list[bool] = []

    class CLI:
        def status(self, live: bool = False) -> None:
            calls.append(live)

    assert FireRunner().run(CLI, command=["status", "--live"], name="raft") is None
    assert calls == [True]


def test_run_fire_rejects_unused_on_callable_object() -> None:
    """Callable treatment path (not used by RaftCLI, but covered for fail-fast)."""
    leaf = _Leaf()
    try:
        FireRunner().run({"go": leaf}, command=["go", "--leiv"], name="raft")
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_run_fire_restores_hook_after_success() -> None:
    before = _stock_call()
    FireRunner().run(_Leaf, command=["status"], name="raft")
    assert fire_core._CallAndUpdateTrace is before
    # Stock Fire still runs-then-rejects without our hook.
    try:
        fire.Fire(_Leaf, command=["status", "--leiv"], name="raft")
    except SystemExit:
        pass
    assert fire_core._CallAndUpdateTrace is before
