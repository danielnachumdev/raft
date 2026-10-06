"""Best-effort ACME ensure for ``tls: acme`` apps (CLI path; controller is later)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

from raft.config.settings import load_config
from raft.config.settings_types import AcmeConfig
from raft.models.app import App
from raft.models.stack import Stack

from .account import AcmeAccountStore
from .app_store import AcmeAppStore
from .install import AcmeGateInstall
from .material import AcmeCertMaterial, AcmeCertWriter
from .order import AcmeOrderRunner
from .paths import AcmePaths

logger = logging.getLogger(__name__)


class AcmeEnsure:
    """Issue/renew live ``acme.{pem,key}``; never raise to fail ``raft apply``."""

    def __init__(
        self,
        stack: Stack,
        *,
        order_runner: Optional[AcmeOrderRunner] = None,
        installer: Optional[AcmeGateInstall] = None,
        writer: Optional[AcmeCertWriter] = None,
        store: Optional[AcmeAppStore] = None,
        config: Optional[AcmeConfig] = None,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.stack = stack
        self._paths = AcmePaths(stack.root)
        self._store = store or AcmeAppStore(stack.root)
        self._writer = writer or AcmeCertWriter()
        self._config = config if config is not None else load_config(stack.root).acme
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._installer = installer
        self._order_runner = order_runner

    def run(self, app_names: Optional[Sequence[str]] = None) -> None:
        """Ensure one or all ``tls: acme`` apps; install/reload if material changed."""
        changed = False
        for app in self._targets(app_names):
            try:
                if self.ensure_app(app):
                    changed = True
            except Exception as exc:  # noqa: BLE001 — best-effort
                logger.warning("ACME ensure failed for %s: %s", app.name, exc)
                self._store.record_error(app.name, str(exc))
        if changed:
            self._install_after_change()

    def ensure_app(self, app: App) -> bool:
        """Return True when live material bytes were written."""
        spec = self.stack.spec_for(app)
        if spec.tls != "acme":
            return False
        email = (self._config.email or "").strip()
        if not email:
            self._store.record_error(app.name, "acme.email is not set in settings.yaml")
            return False
        names = list(spec.server_names(app.public_host))
        if self._should_skip(app.name, names):
            return False
        return self._issue(app, names=names, email=email)

    def _targets(self, app_names: Optional[Sequence[str]]) -> list[App]:
        if app_names is None:
            return [a for a in self.stack.apps if self._is_acme(a)]
        out: list[App] = []
        for name in app_names:
            app = self.stack.app(name)
            if self._is_acme(app):
                out.append(app)
        return out

    def _is_acme(self, app: App) -> bool:
        try:
            return self.stack.spec_for(app).tls == "acme"
        except Exception:  # noqa: BLE001
            return False

    def _should_skip(self, app_name: str, names: list[str]) -> bool:
        pem, key = self._paths.cert_files(app_name)
        if not (pem.is_file() and key.is_file()):
            return False
        try:
            material = self._writer.parse_installed(pem)
        except Exception:  # noqa: BLE001 — re-issue corrupt PEMs
            return False
        if tuple(names) != material.names and set(names) != set(material.names):
            return False
        days = material.days_until_expiry(now=self._now())
        return days > float(self._config.renew_days_before_expiry)

    def _issue(self, app: App, *, names: list[str], email: str) -> bool:
        runner = self._order_runner or self._default_runner(email=email)
        key_pem, csr_pem = self._writer.generate_key_and_csr(names)
        fullchain = runner.issue(csr_pem)
        pem, key = self._paths.cert_files(app.name)
        self._writer.install(pem, key, fullchain_pem=fullchain, key_pem=key_pem)
        material = AcmeCertMaterial.from_pem(fullchain)
        self._store.record_success(app.name, names=names, not_after=material.not_after_iso())
        logger.info("ACME issued cert for %s (%s)", app.name, ", ".join(names))
        return True

    def _default_runner(self, *, email: str) -> AcmeOrderRunner:
        account = AcmeAccountStore(self.stack.root)
        directory = self._config.directory
        return AcmeOrderRunner(
            self.stack.root,
            client_factory=lambda: account.client_for(directory_url=directory, email=email),
        )

    def _install_after_change(self) -> None:
        installer = self._installer
        if installer is None:
            return
        installer.apply()
