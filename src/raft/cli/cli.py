"""Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

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
from raft.ops.certs import missing_origin_certs
from raft.ui import say_err

from .utils.argv import ApplyEnvArgvBridge
from .utils.command_progress import CommandProgress
from .utils.fire_run import run_fire
from .utils.logs_argv import LogsArgvNormalizer
from .cli_commands import RaftCLICommands


class RaftCLI:
    """Process entry: Fire dispatch, logging bootstrap, error → exit mapping."""

    def run(self, argv: Optional[list[str]] = None) -> None:
        self.ensure_logging_bootstrap()
        with TraceContext():
            self._run_inside_trace(argv)

    def _main(self, argv: Optional[list[str]] = None) -> int:
        os.environ["PAGER"] = "cat"
        raw = list(argv) if argv is not None else sys.argv[1:]
        bridge = ApplyEnvArgvBridge()
        command, token = bridge.bind(raw)
        command = LogsArgvNormalizer().normalize(command)
        try:
            with CommandProgress(command):
                run_fire(RaftCLICommands, command=command, name="raft")
        finally:
            bridge.reset(token)
        return 0

    def ensure_logging_bootstrap(self) -> None:
        root = logging.getLogger("raft")
        if root.handlers:
            return
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.INFO)
        root.propagate = False

    def suggest_doctor(
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

    def _run_inside_trace(self, argv: Optional[list[str]]) -> None:
        try:
            raise SystemExit(self._main(argv))
        except subprocess.CalledProcessError as exc:
            self._exit_called_process(argv, exc)
        except Exception as exc:
            self._exit_mapped(argv, exc)

    def _exit_mapped(self, argv: Optional[list[str]], exc: BaseException) -> None:
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

    def _exit_called_process(
        self,
        argv: Optional[list[str]],
        exc: subprocess.CalledProcessError,
    ) -> None:
        shown = self._format_called_process_error(exc)
        self.suggest_doctor(argv, message=shown)
        raise SystemExit(exc.returncode) from exc

    def _exit_operator(
        self,
        argv: Optional[list[str]],
        err: BaseException,
        code: int,
    ) -> None:
        say_err(str(err))
        self.suggest_doctor(argv, message=str(err), err=err)
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
            return missing_origin_certs(load_stack())
        except Exception:  # noqa: BLE001 — best-effort enrichment only
            return None
