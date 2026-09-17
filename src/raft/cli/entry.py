"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional, Union

import fire
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
from ..services.certs import missing_origin_certs
from ..ui import say_err
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
    command = list(argv) if argv is not None else None
    fire.Fire(RaftCLI, command=command, name="raft")
    return 0


def run(argv: Optional[list[str]] = None) -> None:
    _ensure_logging_bootstrap()
    try:
        raise SystemExit(main(argv))
    except subprocess.CalledProcessError as exc:
        shown = _format_called_process_error(exc)
        _suggest_doctor(argv, message=shown)
        raise SystemExit(exc.returncode) from exc
    except yaml.YAMLError as exc:
        err = invalid_yaml("~/.raft/settings.yaml or an App manifest", exc)
        say_err(str(err))
        _suggest_doctor(argv, message=str(err), err=err)
        raise SystemExit(1) from exc
    except OSError as exc:
        err = filesystem_error(exc)
        say_err(str(err))
        _suggest_doctor(argv, message=str(err), err=err)
        raise SystemExit(1) from exc
    except OperatorError as exc:
        say_err(str(exc))
        _suggest_doctor(argv, message=str(exc), err=exc)
        raise SystemExit(1) from exc
    except (RuntimeError, TimeoutError, ValueError, FileNotFoundError) as exc:
        say_err(str(exc))
        _suggest_doctor(argv, message=str(exc), err=exc)
        raise SystemExit(1) from exc
