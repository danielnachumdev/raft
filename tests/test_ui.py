"""Plain terminal output helpers."""

import logging

from raft.ui import say, say_err


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
