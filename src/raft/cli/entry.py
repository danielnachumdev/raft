"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

import fire

from .root import RaftCLI
from ..ui import say_err

def _ensure_logging_bootstrap() -> None:
    root = logging.getLogger("raft")
    if root.handlers:
        return
    root.addHandler(logging.NullHandler())
    root.setLevel(logging.INFO)
    root.propagate = False

def _suggest_doctor(argv: Optional[list[str]]) -> None:
    if argv and argv[0] == "doctor":
        return
    say_err("")
    say_err("Hint: run `raft doctor` to check setup and see fixes.")

def main(argv: Optional[list[str]] = None) -> int:
    os.environ["PAGER"] = "cat"
    command = list(argv) if argv is not None else None
    fire.Fire(RaftCLI, command=command, name="raft")
    return 0

def run(argv: Optional[list[str]] = None) -> None:
    _ensure_logging_bootstrap()
    try:
        raise SystemExit(main(argv))
    except subprocess.CalledProcessError as exc:
        say_err(
            f"command failed ({exc.returncode}): {' '.join(map(str, exc.cmd))}"
        )
        err = (exc.stderr or "").strip()
        if err:
            say_err(err)
        _suggest_doctor(argv)
        raise SystemExit(exc.returncode) from exc
    except (RuntimeError, TimeoutError, KeyError, ValueError, FileNotFoundError) as exc:
        say_err(str(exc))
        _suggest_doctor(argv)
        raise SystemExit(1) from exc
