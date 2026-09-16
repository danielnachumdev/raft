"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

import fire

from ..services.certs import looks_like_missing_origin_cert, missing_origin_certs
from ..ui import say_err
from .root import RaftCLI


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
    say_err("Hint: run `raft doctor` to check setup and see fixes.", style="warn")


def _format_called_process_error(exc: subprocess.CalledProcessError) -> None:
    """Print a CalledProcessError; rewrite known nginx/cert failures into PEM guidance."""
    detail = (exc.stderr or exc.output or "").strip()
    cmd = " ".join(map(str, exc.cmd))
    blob = f"{cmd}\n{detail}"
    if looks_like_missing_origin_cert(blob):
        try:
            from ..models.stack import load_stack

            missing = missing_origin_certs(load_stack())
        except Exception:  # noqa: BLE001 — best-effort enrichment only
            missing = []
        if missing:
            say_err("cannot deploy/reload gate: Cloudflare Origin certs missing:")
            for item in missing:
                say_err(f"  {item.app_name}: {item.detail}")
                say_err(f"    fix: {item.fix}")
            return
        say_err(
            "gate nginx could not load Origin TLS certificates "
            "(missing files under ~/.raft/certs/<app>/)."
        )
        if detail:
            say_err(detail)
        return
    say_err(f"command failed ({exc.returncode}): {cmd}")
    if detail:
        say_err(detail)


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
        _format_called_process_error(exc)
        _suggest_doctor(argv)
        raise SystemExit(exc.returncode) from exc
    except (RuntimeError, TimeoutError, KeyError, ValueError, FileNotFoundError) as exc:
        say_err(str(exc))
        _suggest_doctor(argv)
        raise SystemExit(1) from exc
