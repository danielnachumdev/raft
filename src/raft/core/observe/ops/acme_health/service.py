"""Doctor health for ``tls: acme`` live material and settings prerequisites."""

from datetime import datetime, timezone
from typing import Callable, Optional

from raft.core.lifecycle.acme.app_store import AcmeAppStore
from raft.core.lifecycle.acme.material import AcmeCertMaterial, AcmeCertWriter
from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import AcmeConfig, EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from ..certs import MissingAcmeCerts
from .outcome import AcmeHealthOutcome


class AcmeCertHealth:
    """Per-app ACME cert check: edge/email, presence, expiry, lastError."""

    def __init__(
        self,
        stack: Stack,
        *,
        now: Optional[Callable[[], datetime]] = None,
        writer: Optional[AcmeCertWriter] = None,
        store: Optional[AcmeAppStore] = None,
    ) -> None:
        self._stack = stack
        self._paths = AcmePaths(stack.root)
        self._store = store or AcmeAppStore(stack.root)
        self._writer = writer or AcmeCertWriter()
        self._now = now or (lambda: datetime.now(timezone.utc))

    def check(
        self, app: App, missing: Optional[MissingAcmeCerts]
    ) -> AcmeHealthOutcome:
        edge, acme = self._settings()
        early = self._prereq_fail(edge, acme)
        if early is not None:
            return early
        if missing is not None:
            return self._missing_result(app, missing)
        return self._installed_result(app, acme)

    def _settings(self) -> tuple[EdgeConfig, AcmeConfig]:
        cfg = SettingsLoader().load(self._stack.root)
        return cfg.edge, cfg.acme

    def _prereq_fail(
        self,
        edge: EdgeConfig,
        acme: AcmeConfig,
    ) -> Optional[AcmeHealthOutcome]:
        if edge.http is None:
            return AcmeHealthOutcome(
                "fail",
                "edge.http is null (ACME HTTP-01 needs published :80)",
                fix=(
                    "set edge.http: 80 in ~/.raft/host/settings.yaml, then "
                    "`raft gate recreate`"
                ),
            )
        if not (acme.email or "").strip():
            return AcmeHealthOutcome(
                "fail",
                "acme.email is not set in settings.yaml",
                fix="set acme.email in ~/.raft/host/settings.yaml, then re-apply",
            )
        return None

    def _missing_result(
        self, app: App, missing: MissingAcmeCerts
    ) -> AcmeHealthOutcome:
        state = self._store.load(app.name)
        detail = missing.detail
        if state.last_error:
            detail = f"{detail}; lastError: {state.last_error}"
        return AcmeHealthOutcome("fail", detail, fix=missing.fix)

    def _installed_result(self, app: App, acme: AcmeConfig) -> AcmeHealthOutcome:
        pem, _key = self._paths.cert_files(app.name)
        try:
            material = self._writer.parse_installed(pem)
        except Exception as exc:  # noqa: BLE001
            return AcmeHealthOutcome(
                "fail",
                f"services/{app.name}/certs/acme.pem unreadable: {exc}",
                fix="re-apply so ACME can re-issue, or remove corrupt PEMs",
            )
        return self._expiry_result(app, material, acme)

    def _expiry_result(
        self,
        app: App,
        material: AcmeCertMaterial,
        acme: AcmeConfig,
    ) -> AcmeHealthOutcome:
        days = material.days_until_expiry(now=self._now())
        state = self._store.load(app.name)
        not_after = material.not_after_iso()
        if days < 0:
            return self._expired(app, not_after, state.last_error)
        if days <= float(acme.renew_days_before_expiry):
            return self._near_expiry(app, days, not_after, state.last_error)
        return self._fresh_or_stale(app, not_after, state.last_error)

    def _expired(
        self, app: App, not_after: str, last_error: Optional[str]
    ) -> AcmeHealthOutcome:
        return AcmeHealthOutcome(
            "fail",
            f"ACME cert expired (notAfter {not_after})",
            fix=self._renew_fix(app, last_error),
        )

    def _fresh_or_stale(
        self, app: App, not_after: str, last_error: Optional[str]
    ) -> AcmeHealthOutcome:
        if last_error:
            return AcmeHealthOutcome(
                "warn",
                f"services/{app.name}/certs/acme.pem+key (notAfter {not_after}); "
                f"lastError: {last_error}",
                fix=self._renew_fix(app, last_error),
            )
        return AcmeHealthOutcome(
            "ok",
            f"services/{app.name}/certs/acme.pem+key (notAfter {not_after})",
        )

    def _near_expiry(
        self,
        app: App,
        days: float,
        not_after: str,
        last_error: Optional[str],
    ) -> AcmeHealthOutcome:
        detail = f"ACME cert renews soon (notAfter {not_after}, ~{days:.0f}d left)"
        if last_error:
            detail = f"{detail}; lastError: {last_error}"
        return AcmeHealthOutcome(
            "warn",
            detail,
            fix=self._renew_fix(app, last_error),
        )

    @staticmethod
    def _renew_fix(app: App, last_error: Optional[str]) -> str:
        base = (
            f"controller retries ACME for {app.name} about every 6h; "
            f"check DNS A/AAAA, edge.http (:80), acme.email, and "
            f"~/.raft/services/{app.name}/acme/state.json"
        )
        if last_error and "rate" in last_error.lower():
            return f"{base}; rate-limited — wait or use acme.directory staging"
        return base
