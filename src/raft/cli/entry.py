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


def _suggest_doctor(argv: Optional[list[str]] = None, *, message: str = "") -> None:
    if argv and argv[0] == "doctor":
        return
    # Errors that already include an explicit fix should not add a second CTA.
    lowered = message.lower()
    if "fix:" in lowered or "fix (" in lowered:
        return
    say_err("")
    say_err("Hint: run `raft doctor` to check setup and see fixes.", style="warn")


def _format_called_process_error(exc: subprocess.CalledProcessError) -> str:
    """Print a CalledProcessError; rewrite known failures into a single fix path.

    Returns the text that was shown (for doctor-hint suppression).
    """
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
            lines = ["cannot deploy/reload gate: Cloudflare Origin certs missing:"]
            for item in missing:
                lines.append(f"  {item.app_name}: {item.detail}")
                lines.append(f"    fix: {item.fix}")
            text = "\n".join(lines)
            say_err(text)
            return text
        text = (
            "gate nginx could not load Origin TLS certificates "
            "(missing files under ~/.raft/certs/<app>/)."
        )
        say_err(text)
        if detail:
            say_err(detail)
            return f"{text}\n{detail}"
        return text
    from ..services.registry import (
        looks_like_registry_unauthorized,
        registry_unauthorized_message,
    )

    if "docker" in cmd and "pull" in cmd and looks_like_registry_unauthorized(blob):
        # cmd like: docker pull ghcr.io/org/image:tag
        parts = cmd.split()
        image = parts[-1] if parts else "image"
        text = registry_unauthorized_message(image, detail=detail)
        say_err(text)
        return text
    lines = [f"command failed ({exc.returncode}): {cmd}"]
    if detail:
        lines.append(detail)
    text = "\n".join(lines)
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
    except (RuntimeError, TimeoutError, KeyError, ValueError, FileNotFoundError) as exc:
        say_err(str(exc))
        _suggest_doctor(argv, message=str(exc))
        raise SystemExit(1) from exc
