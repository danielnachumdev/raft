"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional, Union

import yaml

from raft.errors import (
    OperatorError,
    SubprocessCtx,
    classify_subprocess,
    filesystem_error,
    generic_command_failed,
    invalid_yaml,
)

from ..models.stack import load_stack
from ..services.ops.certs import missing_origin_certs
from ..ui import say_err
from .argv import ApplyEnvArgvBridge
from .fire_run import run_fire
from .root import RaftCLI


def _ensure_logging_bootstrap() -> None:
    root = logging.getLogger("raft")
    if root.handlers:
        return
    root.addHandler(logging.NullHandler())
    root.setLevel(logging.INFO)
    root.propagate = False


def _suggest_doctor(
    argv: Optional[list[str]] = None,
    *,
    message: str = "",
    err: Optional[BaseException] = None,
) -> None:
    if argv and argv[0] == "doctor":
        return
    if isinstance(err, OperatorError) and err.has_fix:
        return
    # Fallback for legacy RuntimeError strings that already include Fix.
    lowered = message.lower()
    if "fix:" in lowered or "fix (" in lowered:
        return
    say_err("")
    say_err("Hint: run `raft doctor` to check setup and see fixes.", style="warn")


def _format_called_process_error(exc: subprocess.CalledProcessError) -> str:
    """Classify a CalledProcessError into an operator CTA and print it."""
    missing = None
    try:
        missing = missing_origin_certs(load_stack())
    except Exception:  # noqa: BLE001 — best-effort enrichment only
        missing = None
    ctx = SubprocessCtx(missing_certs=missing)
    err = classify_subprocess(exc, ctx) or generic_command_failed(exc)
    text = str(err)
    say_err(text)
    return text


def main(argv: Optional[list[str]] = None) -> int:
    os.environ["PAGER"] = "cat"
    raw = list(argv) if argv is not None else sys.argv[1:]
    bridge = ApplyEnvArgvBridge()
    command, token = bridge.bind(raw)
    try:
        run_fire(RaftCLI, command=command, name="raft")
    finally:
        bridge.reset(token)
    return 0


def run(argv: Optional[list[str]] = None) -> None:
    _ensure_logging_bootstrap()
    try:
        raise SystemExit(main(argv))
    except subprocess.CalledProcessError as exc:
        _exit_called_process(argv, exc)
    except yaml.YAMLError as exc:
        _exit_operator(argv, invalid_yaml("~/.raft/settings.yaml or an App manifest", exc), 1)
    except OSError as exc:
        _exit_operator(argv, filesystem_error(exc), 1)
    except OperatorError as exc:
        _exit_operator(argv, exc, 1)
    except (RuntimeError, TimeoutError, ValueError, FileNotFoundError) as exc:
        _exit_operator(argv, exc, 1)


def _exit_called_process(argv, exc: subprocess.CalledProcessError) -> None:
    shown = _format_called_process_error(exc)
    _suggest_doctor(argv, message=shown)
    raise SystemExit(exc.returncode) from exc


def _exit_operator(argv, err, code: int) -> None:
    say_err(str(err))
    _suggest_doctor(argv, message=str(err), err=err)
    raise SystemExit(code) from err
