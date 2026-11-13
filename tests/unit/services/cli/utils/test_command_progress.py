"""Early CommandProgress for long verbs before RaftCLICommands init."""

from typing import ClassVar, List
from unittest.mock import patch

from raft.services.cli.utils.command_progress import CommandProgress
from raft.core.core.ui.progress import TerminalProgress


class _SpinnerProbeCLI:
    """Records construction while asserting an early spinner is already active."""

    order: ClassVar[List[str]] = []

    def __init__(self) -> None:
        type(self).order.append("cli_init")
        assert TerminalProgress.active() is not None

    def doctor(self) -> None:
        type(self).order.append("doctor")


def _recording_fire(order: List[str]):
    def fire(*_args, component=None, **_kwargs):
        order.append("fire")
        # Bound method mock: (self, component, ...); function mock: (component, ...).
        # RaftCLI passes an already-built root instance so Fire can show groups on --help.
        target = component if component is not None else _args[-1]
        target.doctor()
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

    def test_enters_spinner_for_redeploy(self) -> None:
        with CommandProgress(["redeploy", "demo-api"]) as progress:
            assert progress is not None
            assert progress._prefix == "raft redeploy"
            assert progress._default_label == "redeploying"

    def test_enters_spinner_for_render(self) -> None:
        with CommandProgress(["render"]) as progress:
            assert progress is not None
            assert progress._prefix == "raft render"
            assert progress._default_label == "rendering"

    def test_enters_spinner_for_apply_sync_up_down(self) -> None:
        for verb, label in (
            ("apply", "applying"),
            ("sync", "syncing"),
            ("up", "starting"),
            ("down", "stopping"),
            ("delete", "deleting"),
            ("uninstall", "uninstalling"),
        ):
            with CommandProgress([verb]) as progress:
                assert progress is not None
                assert progress._prefix == f"raft {verb}"
                assert progress._default_label == label

    def test_quiet_for_get_and_logs(self) -> None:
        for verb in ("get", "logs", "serve", "status"):
            with CommandProgress([verb]) as progress:
                assert progress is None

    def test_main_starts_spinner_before_raftcli_init(self) -> None:
        order = _SpinnerProbeCLI.order
        with patch(
            "raft.services.cli.utils.fire_run.FireRunner.run",
            side_effect=_recording_fire(order),
        ):
            with patch("raft.services.cli.cli.RaftCLICommands", _SpinnerProbeCLI):
                from raft.services.cli import RaftCLI

                assert RaftCLI()._invoke_fire(["doctor"]) == 0
        assert order == ["cli_init", "fire", "doctor"]
        assert TerminalProgress.active() is None
