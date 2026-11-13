"""ActiveShellChild process-group terminate helpers."""

import signal
import subprocess
from unittest.mock import MagicMock, patch

from raft.core.platform.adapters.shell.active_child import ActiveShellChild


class TestActiveShellChild:
    def setup_method(self) -> None:
        ActiveShellChild._current = None

    def teardown_method(self) -> None:
        ActiveShellChild._current = None

    def test_register_clear_and_terminate_active(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None
        proc.pid = 99
        ActiveShellChild.register(proc)
        with patch.object(ActiveShellChild, "terminate") as terminate:
            ActiveShellChild.terminate_active()
        terminate.assert_called_once_with(proc)
        ActiveShellChild.clear(proc)
        with patch.object(ActiveShellChild, "terminate") as terminate:
            ActiveShellChild.terminate_active()
        terminate.assert_not_called()

    def test_terminate_noop_when_already_exited(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = 0
        with patch("raft.core.platform.adapters.shell.active_child.os.killpg") as killpg:
            ActiveShellChild.terminate(proc)
        killpg.assert_not_called()

    def test_terminate_sigterm_then_sigkill(self) -> None:
        proc = MagicMock()
        proc.pid = 77
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd=["x"], timeout=3), 0]
        with patch("raft.core.platform.adapters.shell.active_child.os.killpg") as killpg:
            ActiveShellChild.terminate(proc)
        assert [c.args[1] for c in killpg.call_args_list] == [
            signal.SIGTERM,
            signal.SIGKILL,
        ]

    def test_terminate_sigterm_enough(self) -> None:
        proc = MagicMock()
        proc.pid = 55
        proc.poll.return_value = None
        proc.wait.return_value = 0
        with patch("raft.core.platform.adapters.shell.active_child.os.killpg") as killpg:
            ActiveShellChild.terminate(proc)
        killpg.assert_called_once_with(55, signal.SIGTERM)

    def test_signal_group_ignores_lookup_error(self) -> None:
        proc = MagicMock()
        proc.pid = 1
        with patch(
            "raft.core.platform.adapters.shell.active_child.os.killpg",
            side_effect=ProcessLookupError,
        ):
            ActiveShellChild._signal_group(proc, signal.SIGTERM)

    def test_clear_ignores_other_proc(self) -> None:
        kept = MagicMock()
        other = MagicMock()
        ActiveShellChild.register(kept)
        ActiveShellChild.clear(other)
        assert ActiveShellChild._current is kept

    def test_signal_group_logs_permission_error(self) -> None:
        proc = MagicMock()
        proc.pid = 3
        with patch(
            "raft.core.platform.adapters.shell.active_child.os.killpg",
            side_effect=PermissionError,
        ):
            ActiveShellChild._signal_group(proc, signal.SIGTERM)
