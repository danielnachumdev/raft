"""CliSignalGuard maps SIGINT/SIGTERM to KeyboardInterrupt after child stop."""

import signal
from unittest.mock import patch

import pytest

from raft.services.cli.exit_mapper import CliExitMapper
from raft.services.cli.utils.signal_guard import CliSignalGuard


class TestCliSignalGuard:
    def test_sigterm_raises_keyboard_interrupt(self) -> None:
        with CliSignalGuard():
            with patch(
                "raft.services.cli.utils.signal_guard.ActiveShellChild.terminate_active"
            ) as terminate:
                with pytest.raises(KeyboardInterrupt):
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        terminate.assert_called_once()

    def test_sigint_raises_keyboard_interrupt(self) -> None:
        with CliSignalGuard():
            with patch(
                "raft.services.cli.utils.signal_guard.ActiveShellChild.terminate_active"
            ) as terminate:
                with pytest.raises(KeyboardInterrupt):
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        terminate.assert_called_once()

    def test_restores_previous_handlers(self) -> None:
        before_int = signal.getsignal(signal.SIGINT)
        before_term = signal.getsignal(signal.SIGTERM)
        with CliSignalGuard():
            assert signal.getsignal(signal.SIGINT) is not before_int
        assert signal.getsignal(signal.SIGINT) is before_int
        assert signal.getsignal(signal.SIGTERM) is before_term

    def test_guarded_run_maps_sigterm_path_to_exit_130(self) -> None:
        mapper = CliExitMapper()

        def boom(_argv):
            raise KeyboardInterrupt

        with patch("raft.services.cli.exit_mapper.OperatorSay.say_err") as say:
            with pytest.raises(SystemExit) as caught:
                with CliSignalGuard():
                    mapper.run_guarded(boom, ["redeploy", "demo-api"])
        assert caught.value.code == 130
        say.assert_called_once()
