"""Operator-facing terminal output helpers."""

import logging
import sys

from raft.ui import GREEN, RED, RESET, paint, say, say_err, want_color


def test_say_prints_and_logs(capsys, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="raft"):
        say("hello operator")
        say("")
    out = capsys.readouterr().out
    assert "hello operator" in out
    assert "hello operator" in caplog.text


def test_say_err_prints_stderr_and_logs(capsys, caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="raft"):
        say_err("boom")
    err = capsys.readouterr().err
    assert "boom" in err
    assert "boom" in caplog.text


def test_want_color_respects_no_color_force_and_tty(monkeypatch) -> None:
    class Tty:
        def isatty(self) -> bool:
            return True

    class NoTty:
        def isatty(self) -> bool:
            return False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert want_color(Tty()) is True
    assert want_color(NoTty()) is False

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert want_color() is True
    assert want_color(object()) is False

    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert want_color(Tty()) is False

    monkeypatch.delenv("NO_COLOR", raising=False)
    assert want_color(NoTty()) is True

    assert want_color(NoTty(), explicit=True) is True
    assert want_color(Tty(), explicit=False) is False


def test_paint_and_styled_say(monkeypatch, capsys, caplog) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert paint("x", GREEN) == f"{GREEN}x{RESET}"
    assert paint("x", GREEN, color=False) == "x"
    assert paint("x") == "x"

    with caplog.at_level(logging.INFO, logger="raft"):
        say("ok-msg", style="ok")
        say("plain-unknown", style="nope")
        say_err("err-msg")
        say_err("")
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [f"{GREEN}ok-msg{RESET}", "plain-unknown"]
    assert f"{RED}" in captured.err and "err-msg" in captured.err
    assert "ok-msg" in caplog.text
    assert "\033[" not in caplog.text
