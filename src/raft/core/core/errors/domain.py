"""Named domain OperatorError factories (declarative call-site CTAs)."""

from pathlib import Path
from typing import Any, Optional, Sequence, Union

from .operator_error import OperatorError

__all__ = ["DomainErrors"]


class DomainErrors:
    """Declarative OperatorError factories for CLI / deploy / serve call sites."""

    @staticmethod
    def unknown_app(name: str, known: str) -> OperatorError:
        return OperatorError(
            f"unknown app {name!r} (known: {known}).\n"
            f"Fix: raft get apps   # then apply or pick a listed name"
        )

    @staticmethod
    def unknown_logs_target(name: str, known: str) -> OperatorError:
        return OperatorError(
            f"unknown logs target {name!r} (known: {known}).\n"
            f"Fix: raft logs <app|gate|router|controller|dashboard>   # see: raft get apps"
        )

    @staticmethod
    def app_not_applied(name: str, known: str) -> OperatorError:
        return OperatorError(
            f"app {name!r} is not applied (known: {known}).\n" f"Fix: raft get apps"
        )

    @staticmethod
    def service_not_running(service: str) -> OperatorError:
        return OperatorError(
            f"service {service!r} is not running — bring the stack up first.\n" f"Fix: raft up"
        )

    @staticmethod
    def serve_already_running(port: int) -> OperatorError:
        return OperatorError(
            f"raft serve is already running on 127.0.0.1:{port}.\n"
            f"Fix: raft serve --stop\n"
            f"     raft serve --port=<other>   # or listen on a free port"
        )

    @staticmethod
    def serve_stop_failed(port: int, pid: int, detail: str) -> OperatorError:
        who = f"pid {pid}" if pid else "unknown pid"
        return OperatorError(
            f"could not stop raft serve on 127.0.0.1:{port} ({who}): {detail}.\n"
            f"Fix: raft serve --stop --port={port}\n"
            f"     # or stop the process holding ~/.raft/host/serve/port-{port}.lock"
        )

    @staticmethod
    def stack_already_running(
        running: Sequence[str], *, holders: Sequence[str] = ()
    ) -> OperatorError:
        joined = ", ".join(running)
        hold = ", ".join(holders) if holders else "(none listed)"
        return OperatorError(
            f"stack already running ({joined}). "
            f"Refusing to rebuild/reload everything.\n"
            f"Network holders on raft_default: {hold}\n"
            f"Fix: docker compose -f ~/.raft/compose.yaml ps\n"
            f"     raft down                    # must finish with no running services\n"
            f"     # if down warned 'Network … still in use', another process may have\n"
            f"     # restarted containers — run raft down again, then:\n"
            f"     docker compose -f ~/.raft/compose.yaml ps   # expect empty / Exited\n"
            f"     raft up\n"
            f"     # targeted update instead of full rebuild: raft redeploy <app|router>",
            has_fix=False,
        )

    @staticmethod
    def stack_down_incomplete(
        running: Sequence[str], *, holders: Sequence[str] = ()
    ) -> OperatorError:
        joined = ", ".join(running) if running else "(none)"
        hold = ", ".join(holders) if holders else "(none listed)"
        return OperatorError(
            f"raft down did not fully stop the stack — still running: {joined}.\n"
            f"Network holders on raft_default: {hold}\n"
            f"Fix: docker compose -f ~/.raft/compose.yaml ps\n"
            f"     docker compose -f ~/.raft/compose.yaml down --remove-orphans\n"
            f"     # if something immediately restarts (other terminal/CI), stop it first\n"
            f"     raft down && raft up"
        )

    @staticmethod
    def redeploy_requires_app() -> OperatorError:
        return OperatorError("redeploy requires APP.\n" "Fix: raft redeploy <app>|router")

    @staticmethod
    def apply_requires_source() -> OperatorError:
        return OperatorError(
            "apply requires --file PATH or --git URL.\n"
            "Fix: raft apply --file path/to/app.yaml"
        )

    @staticmethod
    def deploy_lock_busy(kind: str, path: Union[Path, str]) -> OperatorError:
        return OperatorError(
            f"another raft operation holds the {kind} lock "
            f"(timed out waiting for {path}).\n"
            f"Fix: wait for the other apply/redeploy/render to finish, then retry; "
            f"or raise RAFT_LOCK_TIMEOUT_SECONDS (default 300)"
        )

    @staticmethod
    def invalid_lock_timeout(raw: object) -> OperatorError:
        return OperatorError(
            f"RAFT_LOCK_TIMEOUT_SECONDS must be a non-negative number, got {raw!r}.\n"
            f"Fix: unset it or set e.g. RAFT_LOCK_TIMEOUT_SECONDS=300"
        )

    @staticmethod
    def auth_requires_service(cmd: str) -> OperatorError:
        return OperatorError(
            f"auth {cmd} requires SERVICE.\n"
            f"Fix: raft auth {cmd} <app-name> [--repo git@host:owner/repo.git]"
        )

    @staticmethod
    def missing_manifest(path: Path) -> OperatorError:
        return OperatorError(
            f"cannot read App manifest: {path}\n"
            f"Fix: pass an existing path (e.g. .raft/app.yaml) or use: "
            f"raft apply --git git@host:owner/repo.git"
        )

    @staticmethod
    def depends_on_cycle(name: str, detail: str) -> OperatorError:
        return OperatorError(
            f"dependsOn cycle while applying {name!r}: {detail}\n"
            f"Fix: raft get apps\n"
            f"     # edit manifests so dependsOn is a DAG (no A→B→A / self-loops)\n"
            f"     raft apply --file path/to/app.yaml   # or --git …"
        )

    @staticmethod
    def app_name_source_conflict(
        name: str, *, existing: str, incoming: str
    ) -> OperatorError:
        return OperatorError(
            f"app name {name!r} is already applied from a different source.\n"
            f"  existing: {existing}\n"
            f"  incoming: {incoming}\n"
            f"Fix: rename metadata.name in the incoming manifest, or:\n"
            f"     raft delete {name}   # frees the name; then re-apply from the new source\n"
            f"     # v1 has no --force/--replace — delete + re-apply is the reclaim path"
        )

    @staticmethod
    def invalid_yaml(path: Union[Path, str], exc: BaseException) -> OperatorError:
        return OperatorError(f"invalid YAML in {path}: {exc}\n" f"Fix: repair the YAML file")

    @staticmethod
    def filesystem_error(exc: BaseException) -> OperatorError:
        detail = str(exc)
        extra = ""
        if "permission denied" in detail.lower() or getattr(exc, "errno", None) == 13:
            extra = (
                " If raft-controller left root-owned files, fix with:\n"
                '     sudo chown -R "$(whoami):$(whoami)" "${RAFT_DATA_HOME:-$HOME/.raft}"'
            )
        return OperatorError(
            f"filesystem error: {exc}\n"
            f"Fix: check permissions on ~/.raft (or $RAFT_DATA_HOME) and retry.{extra}"
        )

    @staticmethod
    def require_int(
        raw: Any,
        *,
        label: str,
        path: Union[Path, str] = "",
    ) -> int:
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            prefix = f"{path}: " if path else ""
            raise OperatorError(
                f"{prefix}{label} must be an integer (1–65535), got {raw!r}.\n"
                f"Fix: use an unquoted number"
            ) from exc

    @staticmethod
    def require_bool(
        raw: Any,
        *,
        label: str,
        path: Union[Path, str] = "",
        default: Optional[bool] = None,
    ) -> bool:
        if raw is None and default is not None:
            return default
        if not isinstance(raw, bool):
            prefix = f"{path}: " if path else ""
            raise OperatorError(
                f"{prefix}{label} must be a boolean, got {raw!r}.\n"
                f"Fix: use `true` or `false` (unquoted)"
            )
        return raw

    @staticmethod
    def require_mapping(
        raw: Any,
        *,
        label: str,
        path: Union[Path, str] = "",
    ) -> dict:
        if not isinstance(raw, dict):
            prefix = f"{path}: " if path else ""
            raise OperatorError(
                f"{prefix}{label} must be a YAML mapping, got {type(raw).__name__}.\n"
                f"Fix: use a key/value document"
            )
        return raw
