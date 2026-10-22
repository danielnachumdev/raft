"""Parse and validate ``spec.tls`` against ports and publicHost."""

from pathlib import Path
from typing import Any

from raft.core.core.errors.cta import OperatorError

from ..manifest import TLS_MODES
from ..ports import PortSpec


class AppTlsFields:
    """Parse App ``spec.tls`` (off / origin / acme)."""

    @staticmethod
    def parse(
        spec: dict[str, Any],
        path: Path,
        *,
        public_host: str,
        ports: tuple[PortSpec, ...],
    ) -> str:
        tls = AppTlsFields._normalize(spec.get("tls", "off"), path)
        if tls not in TLS_MODES:
            raise OperatorError(
                f"{path}: spec.tls must be one of {sorted(TLS_MODES)}, got {tls!r}.\n"
                f"Fix: set tls: off | origin | acme"
            )
        AppTlsFields._require_host(tls, public_host, path)
        AppTlsFields._require_http_port(tls, ports, path)
        return tls

    @staticmethod
    def _require_host(tls: str, public_host: str, path: Path) -> None:
        if tls in {"origin", "acme"} and not public_host:
            raise OperatorError(
                f"{path}: spec.tls={tls} requires spec.publicHost.\n"
                f"Fix: set publicHost to the HTTPS hostname, or use tls: off"
            )

    @staticmethod
    def _require_http_port(tls: str, ports: tuple[PortSpec, ...], path: Path) -> None:
        if tls not in {"origin", "acme"}:
            return
        if not ports:
            raise OperatorError(
                f"{path}: spec.tls={tls} requires at least one port "
                f"(worker Apps with empty ports use tls: off only).\n"
                f"Fix: add a port, or set tls: off for workers"
            )
        if tls != "acme":
            return
        if any(p.expose == "http" for p in ports):
            return
        raise OperatorError(
            f"{path}: spec.tls=acme requires at least one port with expose: http "
            f"(and publicHost). Stream/host/none-only apps cannot use ACME.\n"
            f"Fix: add an expose: http port, or use tls: origin | off"
        )

    @staticmethod
    def _normalize(raw_tls: Any, path: Path) -> str:
        if isinstance(raw_tls, bool):
            if raw_tls:
                raise OperatorError(
                    f"{path}: spec.tls must be one of {sorted(TLS_MODES)} "
                    f"(YAML true is not valid; use 'origin' or 'acme').\n"
                    f"Fix: set tls: off | origin | acme"
                )
            return "off"
        return str(raw_tls).strip().lower() or "off"
