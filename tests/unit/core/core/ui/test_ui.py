"""Operator-facing terminal output helpers."""

import logging
import sys

from raft.core.core.ui import GREEN, RED, RESET, OperatorSay, TerminalColor


class _Tty:
    def isatty(self) -> bool:
        return True


class _NoTty:
    def isatty(self) -> bool:
        return False


class TestOperatorSay:
    def test_say_prints_and_logs(self, capsys, caplog) -> None:
        with caplog.at_level(logging.INFO, logger="raft"):
            OperatorSay.say("hello operator")
            OperatorSay.say("")
        out = capsys.readouterr().out
        assert "hello operator" in out
        assert "hello operator" in caplog.text

    def test_say_err_prints_stderr_and_logs(self, capsys, caplog) -> None:
        with caplog.at_level(logging.ERROR, logger="raft"):
            OperatorSay.say_err("boom")
        err = capsys.readouterr().err
        assert "boom" in err
        assert "boom" in caplog.text

    def test_paint_and_styled_say(self, monkeypatch, capsys, caplog) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("FORCE_COLOR", "1")
        assert TerminalColor.paint("x", GREEN) == f"{GREEN}x{RESET}"
        assert TerminalColor.paint("x", GREEN, color=False) == "x"
        assert TerminalColor.paint("x") == "x"
        with caplog.at_level(logging.INFO, logger="raft"):
            OperatorSay.say("ok-msg", style="ok")
            OperatorSay.say("plain-unknown", style="nope")
            OperatorSay.say_err("err-msg")
            OperatorSay.say_err("")
        captured = capsys.readouterr()
        assert captured.out.splitlines() == [f"{GREEN}ok-msg{RESET}", "plain-unknown"]
        assert f"{RED}" in captured.err and "err-msg" in captured.err
        assert "ok-msg" in caplog.text
        assert "\033[" not in caplog.text


class TestTerminalColor:
    def test_want_color_respects_no_color_force_and_tty(self, monkeypatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        assert TerminalColor.want(_Tty()) is True
        assert TerminalColor.want(_NoTty()) is False
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert TerminalColor.want() is True
        assert TerminalColor.want(object()) is False
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("FORCE_COLOR", "1")
        assert TerminalColor.want(_Tty()) is False
        monkeypatch.delenv("NO_COLOR", raising=False)
        assert TerminalColor.want(_NoTty()) is True
        assert TerminalColor.want(_NoTty(), explicit=True) is True
        assert TerminalColor.want(_Tty(), explicit=False) is False
