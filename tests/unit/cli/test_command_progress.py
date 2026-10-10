"""Early CommandProgress for doctor/update before RaftCLICommands init."""

from __future__ import annotations

from typing import ClassVar, List
from unittest.mock import patch

from raft.cli.utils.command_progress import CommandProgress
from raft.ui.progress import TerminalProgress


class _SpinnerProbeCLI:
    """Records construction while asserting an early spinner is already active."""

    order: ClassVar[List[str]] = []

    def __init__(self) -> None:
        type(self).order.append("cli_init")
        assert TerminalProgress.active() is not None

    def doctor(self) -> None:
        type(self).order.append("doctor")


def _recording_fire(order: List[str]):
    def fire(component, command=None, name=None):
        order.append("fire")
        component()
        return None

    return fire


class TestCommandProgress:
    def setup_method(self) -> None:
        TerminalProgress._active = None
        _SpinnerProbeCLI.order = []

    def teardown_method(self) -> None:
        TerminalProgress._active = None

    def test_noop_for_other_commands(self) -> None:
        with CommandProgress(["status"]) as progress:
            assert progress is None
            assert TerminalProgress.active() is None

    def test_enters_spinner_for_doctor(self) -> None:
        with CommandProgress(["doctor"]) as progress:
            assert progress is not None
            assert TerminalProgress.current() is progress
            assert progress._prefix == "raft doctor"
        assert TerminalProgress.active() is None

    def test_enters_spinner_for_update(self) -> None:
        with CommandProgress(["update"]) as progress:
            assert progress is not None
            assert progress._prefix == "raft update"
            assert progress._default_label == "updating"

    def test_enters_spinner_for_purge(self) -> None:
        with CommandProgress(["purge"]) as progress:
            assert progress is not None
            assert progress._prefix == "raft purge"
            assert progress._default_label == "purging"

    def test_main_starts_spinner_before_raftcli_init(self) -> None:
        order = _SpinnerProbeCLI.order
        with patch("raft.cli.cli.run_fire", side_effect=_recording_fire(order)):
            with patch("raft.cli.cli.RaftCLICommands", _SpinnerProbeCLI):
                from raft.cli import RaftCLI

                assert RaftCLI()._main(["doctor"]) == 0
        assert order == ["fire", "cli_init"]
        assert TerminalProgress.active() is None
