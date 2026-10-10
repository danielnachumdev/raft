"""TLS cert presence checks for ``tls: origin`` and doctor ``tls: acme`` skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from raft.acme.paths import AcmePaths
from raft.errors.certs_msgs import format_missing_origin_certs
from raft.errors.cta import OperatorError
from raft.models.app import App
from raft.models.stack import Stack


@dataclass(frozen=True)
class MissingOriginCerts:
    app_name: str
    missing: tuple[str, ...]

    @property
    def detail(self) -> str:
        return f"missing {', '.join(self.missing)} under certs/{self.app_name}/"

    @property
    def fix(self) -> str:
        return (
            f"install Cloudflare Origin PEMs for {self.app_name} at "
            f"~/.raft/certs/{self.app_name}/origin.pem and origin.key "
            f"(required for tls: origin; then `raft gate recreate` if needed)"
        )


@dataclass(frozen=True)
class MissingAcmeCerts:
    """Doctor skeleton when ``tls: acme`` live material is not on disk yet."""

    app_name: str
    missing: tuple[str, ...]

    @property
    def detail(self) -> str:
        return f"missing {', '.join(self.missing)} under certs/{self.app_name}/"

    @property
    def fix(self) -> str:
        return (
            f"point DNS A/AAAA for {self.app_name} publicHost (+ extraHosts) at this host; "
            f"keep edge.http (:80) and edge.https (:443) published; set acme.email in "
            f"~/.raft/settings.yaml; then re-apply so ACME can issue "
            f"~/.raft/certs/{self.app_name}/acme.pem and acme.key "
            f"(do not paste Origin PEMs for tls: acme)"
        )


class CertProbe:
    """Probe applied apps for missing ``tls: origin`` / ``tls: acme`` PEMs."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack
        self._acme_paths = AcmePaths(stack.root)

    def missing_origin(self) -> list[MissingOriginCerts]:
        """Return missing PEM/key pairs for every applied app with ``tls: origin``."""
        results: list[MissingOriginCerts] = []
        for app in self._apps_with_tls("origin"):
            pem, key = self._stack.cert_files(app)
            missing = self._absent_names(pem, key)
            if missing:
                results.append(MissingOriginCerts(app.name, missing))
        return results

    def missing_acme(self) -> list[MissingAcmeCerts]:
        """Return missing ACME live pairs for ``tls: acme`` apps (doctor only)."""
        results: list[MissingAcmeCerts] = []
        for app in self._apps_with_tls("acme"):
            pem, key = self._acme_paths.cert_files(app.name)
            missing = self._absent_names(pem, key)
            if missing:
                results.append(MissingAcmeCerts(app.name, missing))
        return results

    def require_origin(self) -> None:
        """Raise if any ``tls: origin`` app is missing PEMs (before gate nginx load)."""
        missing = self.missing_origin()
        if not missing:
            return
        raise OperatorError(
            format_missing_origin_certs(missing, include_doctor_footer=True)
        )

    def _apps_with_tls(self, tls: str) -> Iterator[App]:
        for app in self._stack.apps:
            try:
                app_spec = self._stack.spec_for(app)
            except (ValueError, FileNotFoundError, OperatorError):
                continue
            if app_spec.tls == tls:
                yield app

    @staticmethod
    def _absent_names(pem: Path, key: Path) -> tuple[str, ...]:
        return tuple(p.name for p in (pem, key) if not p.is_file())
