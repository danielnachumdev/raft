"""TLS cert presence checks for ``tls: origin`` and doctor ``tls: acme`` skeleton."""

from pathlib import Path
from typing import Iterator

from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.core.errors.certs_msgs import CertMessages
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from .missing_acme import MissingAcmeCerts
from .missing_origin import MissingOriginCerts


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
            CertMessages.format_missing_origin_certs(missing, include_doctor_footer=True)
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
