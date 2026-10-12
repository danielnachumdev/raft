"""Unit tests for fail-fast Fire unused-arg rejection."""

import fire
from fire import core as fire_core

from raft.cli.utils.fire_run import FireRunner


class _Leaf:
    def status(self, live: bool = False) -> str:
        return "ran"

    def __call__(self, live: bool = False) -> str:
        return "called"


class TestFireRunner:
    def test_rejects_unknown_flag_before_routine(self) -> None:
        calls: list[str] = []
        before = fire_core._CallAndUpdateTrace

        class CLI:
            def status(self, live: bool = False) -> None:
                calls.append("status")

        self._assert_exits_two(CLI, ["status", "--leiv"])
        assert calls == []
        assert fire_core._CallAndUpdateTrace is before

    def test_allows_valid_flags(self) -> None:
        calls: list[bool] = []

        class CLI:
            def status(self, live: bool = False) -> None:
                calls.append(live)

        assert FireRunner().run(CLI, command=["status", "--live"], name="raft") is None
        assert calls == [True]

    def test_rejects_unused_on_callable_object(self) -> None:
        """Callable treatment path (not used by RaftCLI, but covered for fail-fast)."""
        self._assert_exits_two({"go": _Leaf()}, ["go", "--leiv"])

    def test_restores_hook_after_success(self) -> None:
        before = fire_core._CallAndUpdateTrace
        FireRunner().run(_Leaf, command=["status"], name="raft")
        assert fire_core._CallAndUpdateTrace is before
        try:
            fire.Fire(_Leaf, command=["status", "--leiv"], name="raft")
        except SystemExit:
            pass
        assert fire_core._CallAndUpdateTrace is before

    @staticmethod
    def _assert_exits_two(component, command: list) -> None:
        try:
            FireRunner().run(component, command=command, name="raft")
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("expected SystemExit")
