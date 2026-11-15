"""Bounded docker logs fetch — timeout / byte budget."""

from unittest.mock import MagicMock

from raft.core.platform.adapters.docker.bounded_logs import (
    LOG_FETCH_RECENT_TAIL,
    BoundedDockerLogs,
)


class _Stdout:
    def __init__(self, lines: list[str], *, blank_then: str = "") -> None:
        self._lines = list(lines)
        self._blank_then = blank_then
        self._blanks = 0

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        if self._blank_then and self._blanks < 1:
            self._blanks += 1
            return ""
        if self._blank_then:
            out = self._blank_then
            self._blank_then = ""
            return out
        return ""


def _proc(lines: list[str]) -> MagicMock:
    proc = MagicMock()
    proc.stdout = _Stdout(lines)
    proc.poll.return_value = 0
    proc.args = ["docker", "logs"]
    return proc


class TestBoundedDockerLogs:
    def test_empty_name_noop(self) -> None:
        shell = MagicMock()
        assert BoundedDockerLogs(shell).fetch("") == ""
        shell.popen.assert_not_called()

    def test_bootstrap_uses_tail(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        proc.stdout = _Stdout(["2026-10-14T12:00:00Z a\n"])
        proc.poll.return_value = 0
        proc.args = ["docker", "logs"]
        shell.popen.return_value = proc
        text = BoundedDockerLogs(shell).fetch("cid", since="", bootstrap_tail=50)
        assert "a" in text
        assert shell.popen.call_args.args[0] == [
            "docker",
            "logs",
            "--timestamps",
            "--tail",
            "50",
            "cid",
        ]

    def test_since_uses_tail_when_it_reaches_cursor(self) -> None:
        shell = MagicMock()
        shell.popen.return_value = _proc(
            ["2026-10-14T10:59:59.5Z old\n", "2026-10-14T12:00:00Z a\n"]
        )
        text = BoundedDockerLogs(shell).fetch(
            "cid", since="2026-10-14T11:00:00.000000000Z", bootstrap_tail=50
        )
        assert "a" in text
        assert shell.popen.call_count == 1
        args = shell.popen.call_args.args[0]
        assert args[args.index("--tail") + 1] == "50"

    def test_recent_tail_is_capped(self) -> None:
        shell = MagicMock()
        shell.popen.return_value = _proc(["2026-10-14T10:00:00Z a\n"])
        BoundedDockerLogs(shell).fetch(
            "cid", since="2026-10-14T11:00:00Z", bootstrap_tail=100_000
        )
        args = shell.popen.call_args.args[0]
        assert args[args.index("--tail") + 1] == str(LOG_FETCH_RECENT_TAIL)

    def test_since_falls_back_when_tail_starts_after_cursor(self) -> None:
        shell = MagicMock()
        shell.popen.side_effect = [
            _proc(["2026-10-14T12:00:00Z newest\n"]),
            _proc(["2026-10-14T11:30:00Z gap\n", "2026-10-14T12:00:00Z newest\n"]),
        ]
        text = BoundedDockerLogs(shell).fetch("cid", since="2026-10-14T11:00:00Z")
        assert "gap" in text
        assert shell.popen.call_count == 2
        since_args = shell.popen.call_args.args[0]
        assert "--tail" not in since_args
        assert since_args[since_args.index("--since") + 1] == "2026-10-14T11:00:00Z"

    def test_since_falls_back_when_tail_is_truncated(self) -> None:
        shell = MagicMock()
        shell.popen.side_effect = [
            _proc(["2026-10-14T10:00:00Z " + ("x" * 50) + "\n"]),
            _proc(["2026-10-14T12:00:00Z a\n"]),
        ]
        text = BoundedDockerLogs(shell).fetch(
            "cid", since="2026-10-14T11:00:00Z", max_bytes=40
        )
        assert text == "2026-10-14T12:00:00Z a"
        assert shell.popen.call_count == 2

    def test_since_falls_back_when_tail_command_fails(self) -> None:
        shell = MagicMock()
        failed = _proc(["2026-10-14T10:00:00Z a\n"])
        failed.poll.return_value = 1
        shell.popen.side_effect = [failed, _proc(["2026-10-14T12:00:00Z b\n"])]
        text = BoundedDockerLogs(shell).fetch("cid", since="2026-10-14T11:00:00Z")
        assert "b" in text

    def test_max_bytes_exact_fill_exits_loop(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        # Exactly 10 UTF-8 bytes, then another line that must not be read.
        proc.stdout = _Stdout(["1234567890", "SHOULD_NOT\n"])
        proc.poll.return_value = 0
        proc.args = ["docker", "logs"]
        shell.popen.return_value = proc
        text = BoundedDockerLogs(shell).fetch("cid", since="", max_bytes=10)
        assert text == "1234567890"
        assert "SHOULD" not in text

    def test_max_bytes_stops_before_partial_line(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        proc.stdout = _Stdout(
            [
                "2026-10-14T12:00:00Z short\n",
                "2026-10-14T12:00:01Z " + ("x" * 200) + "\n",
            ]
        )
        proc.poll.return_value = None
        proc.args = ["docker", "logs"]
        shell.popen.return_value = proc
        text = BoundedDockerLogs(shell).fetch("cid", since="", max_bytes=40)
        assert "short" in text
        assert "xxx" not in text
        proc.kill.assert_called()

    def test_timeout_kills_process(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        # Never-ending blank reads while still "running" → hit deadline.
        proc.stdout = _Stdout([], blank_then="")
        proc.poll.return_value = None
        proc.args = ["docker", "logs", "cid"]
        shell.popen.return_value = proc
        text = BoundedDockerLogs(shell).fetch("cid", since="", timeout=0.05, max_bytes=9999)
        assert text == ""
        proc.kill.assert_called()

    def test_trim_incomplete_trailing_line(self) -> None:
        assert BoundedDockerLogs._trim_incomplete_line("a\nb") == "a\n"
        assert BoundedDockerLogs._trim_incomplete_line("only") == "only"
        assert BoundedDockerLogs._trim_incomplete_line("a\n") == "a\n"

    def test_stop_handles_already_exited(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = 0
        BoundedDockerLogs._stop(proc)
        proc.kill.assert_not_called()

    def test_stop_swallows_kill_errors(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None
        proc.kill.side_effect = OSError("gone")
        BoundedDockerLogs._stop(proc)

    def test_stop_swallows_wait_timeout(self) -> None:
        import subprocess

        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=2)
        BoundedDockerLogs._stop(proc)

    def test_waits_through_transient_blank_reads(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        proc.stdout = _Stdout([], blank_then="2026-10-14T12:00:00Z late\n")
        # First blank: still running; after late line: exited.
        proc.poll.side_effect = [None, 0, 0, 0]
        proc.args = ["docker", "logs"]
        shell.popen.return_value = proc
        text = BoundedDockerLogs(shell).fetch("cid", since="", timeout=2.0)
        assert "late" in text

    def test_null_stdout(self) -> None:
        shell = MagicMock()
        proc = MagicMock()
        proc.stdout = None
        proc.poll.return_value = 0
        proc.args = ["docker", "logs"]
        shell.popen.return_value = proc
        assert BoundedDockerLogs(shell).fetch("cid", since="") == ""
