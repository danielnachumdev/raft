"""Map CLI failures to operator messages and ``SystemExit``."""

import subprocess
from typing import Callable, Optional

import yaml

from raft.core.core.errors.classify import SubprocessClassifier, SubprocessCtx
from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.certs import CertProbe
from raft.core.core.ui import OperatorSay


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
        OperatorSay.say_err("")
        OperatorSay.say_err("Hint: run `raft doctor` to check setup and see fixes.", style="warn")

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
            return DomainErrors.invalid_yaml("~/.raft/host/settings.yaml or an App manifest", exc)
        if isinstance(exc, OSError):
            return DomainErrors.filesystem_error(exc)
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
        OperatorSay.say_err(str(err))
        self._suggest_doctor(argv, message=str(err), err=err)
        raise SystemExit(code) from err

    def _format_called_process_error(self, exc: subprocess.CalledProcessError) -> str:
        missing = self._missing_certs_best_effort()
        ctx = SubprocessCtx(missing_certs=missing)
        err = SubprocessClassifier().classify(exc, ctx) or SubprocessClassifier.generic_command_failed(exc)
        text = str(err)
        OperatorSay.say_err(text)
        return text

    def _missing_certs_best_effort(self):
        try:
            return CertProbe(load_stack()).missing_origin()
        except Exception:  # noqa: BLE001 — best-effort enrichment only
            return None
