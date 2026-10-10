"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Callable, Optional

import yaml

from raft.config.trace_context import TraceContext
from raft.errors.classify import (
    SubprocessCtx,
    classify_subprocess,
    generic_command_failed,
)
from raft.errors.cta import OperatorError
from raft.errors.domain import (
    filesystem_error,
    invalid_yaml,
)
from raft.models.stack import load_stack
from raft.ops.certs import CertProbe
from raft.ui import say_err

from .utils.argv import ApplyEnvArgvBridge
from .utils.command_progress import CommandProgress
from .utils.fire_run import FireRunner
from .utils.logs_argv import LogsArgvNormalizer
from .cli_commands import RaftCLICommands


class CliExitMapper:
    """Map CLI failures to operator messages and ``SystemExit``."""

    def run_guarded(
        self,
        invoke: Callable[[Optional[list[str]]], int],
        argv: Optional[list[str]],
    ) -> None:
        """Invoke ``invoke``; map operator/subprocess failures to ``SystemExit``."""
        try:
            raise SystemExit(invoke(argv))
        except subprocess.CalledProcessError as exc:
            self._handle(argv, exc)
        except Exception as exc:
            self._fallback_handle(argv, exc)

    def _suggest_doctor(
        self,
        argv: Optional[list[str]] = None,
        *,
        message: str = "",
        err: Optional[BaseException] = None,
    ) -> None:
        if self._should_skip_doctor_hint(argv, message=message, err=err):
            return
        say_err("")
        say_err("Hint: run `raft doctor` to check setup and see fixes.", style="warn")

    def _should_skip_doctor_hint(
        self,
        argv: Optional[list[str]],
        *,
        message: str,
        err: Optional[BaseException],
    ) -> bool:
        if argv and argv[0] == "doctor":
            return True
        if isinstance(err, OperatorError) and err.has_fix:
            return True
        lowered = message.lower()
        return "fix:" in lowered or "fix (" in lowered

    def _fallback_handle(self, argv: Optional[list[str]], exc: BaseException) -> None:
        mapped = self._map_operator_exc(exc)
        if mapped is None:
            raise exc
        self._exit_operator(argv, mapped, 1)

    def _map_operator_exc(self, exc: BaseException) -> Optional[BaseException]:
        if isinstance(exc, yaml.YAMLError):
            return invalid_yaml("~/.raft/settings.yaml or an App manifest", exc)
        if isinstance(exc, OSError):
            return filesystem_error(exc)
        if isinstance(exc, OperatorError):
            return exc
        if isinstance(exc, (RuntimeError, TimeoutError, ValueError, FileNotFoundError)):
            return exc
        return None

    def _handle(
        self,
        argv: Optional[list[str]],
        exc: subprocess.CalledProcessError,
    ) -> None:
        shown = self._format_called_process_error(exc)
        self._suggest_doctor(argv, message=shown)
        raise SystemExit(exc.returncode) from exc

    def _exit_operator(
        self,
        argv: Optional[list[str]],
        err: BaseException,
        code: int,
    ) -> None:
        say_err(str(err))
        self._suggest_doctor(argv, message=str(err), err=err)
        raise SystemExit(code) from err

    def _format_called_process_error(self, exc: subprocess.CalledProcessError) -> str:
        missing = self._missing_certs_best_effort()
        ctx = SubprocessCtx(missing_certs=missing)
        err = classify_subprocess(exc, ctx) or generic_command_failed(exc)
        text = str(err)
        say_err(text)
        return text

    def _missing_certs_best_effort(self):
        try:
            return CertProbe(load_stack()).missing_origin()
        except Exception:  # noqa: BLE001 — best-effort enrichment only
            return None


class RaftCLI:
    """Process entry: logging bootstrap, trace context, Fire dispatch."""

    def __init__(self) -> None:
        self._exits = CliExitMapper()
        self._fire = FireRunner()

    def run(self, argv: Optional[list[str]] = None) -> None:
        """Bootstrap logging, open a request trace, then run one CLI invocation."""
        self._ensure_logging_bootstrap()
        with TraceContext():
            self._exits.run_guarded(self._invoke_fire, argv)

    def _invoke_fire(self, argv: Optional[list[str]] = None) -> int:
        """Normalize argv and dispatch to ``RaftCLICommands`` via Fire."""
        os.environ["PAGER"] = "cat"
        raw = list(argv) if argv is not None else sys.argv[1:]
        bridge = ApplyEnvArgvBridge()
        command, token = bridge.bind(raw)
        command = LogsArgvNormalizer().normalize(command)
        try:
            with CommandProgress(command):
                self._fire.run(RaftCLICommands, command=command, name="raft")
        finally:
            bridge.reset(token)
        return 0

    def _ensure_logging_bootstrap(self) -> None:
        root = logging.getLogger("raft")
        if root.handlers:
            return
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.INFO)
        root.propagate = False
