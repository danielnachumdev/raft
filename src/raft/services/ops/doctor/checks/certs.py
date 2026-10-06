"""TLS cert presence checks (``tls: origin`` and ``tls: acme`` skeleton)."""

from __future__ import annotations

from typing import Optional

from raft.errors.cta import OperatorError

from ...certs import missing_acme_certs, missing_origin_certs
from ..context import DoctorContext
from ..models import CheckResult


class CertChecks:
    name = "certs"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        origin_missing = {m.app_name: m for m in missing_origin_certs(ctx.stack)}
        acme_missing = {m.app_name: m for m in missing_acme_certs(ctx.stack)}
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            result = self._check_app(ctx, app, origin_missing, acme_missing)
            if result is not None:
                results.append(result)
        return results

    def _check_app(
        self,
        ctx: DoctorContext,
        app,
        origin_missing,
        acme_missing,
    ) -> Optional[CheckResult]:
        try:
            app_spec = ctx.stack.spec_for(app)
        except (ValueError, FileNotFoundError, OperatorError):
            return None
        if app_spec.tls == "acme":
            return self._acme_result(app, acme_missing)
        if app_spec.tls != "origin":
            return CheckResult(app.compose_id, "certs", "ok", "n/a (tls: off)")
        return self._origin_result(app, origin_missing)

    @staticmethod
    def _origin_result(app, origin_missing) -> CheckResult:
        item = origin_missing.get(app.name)
        if item is None:
            return CheckResult(
                app.compose_id,
                "certs",
                "ok",
                f"certs/{app.name}/origin.pem+key",
            )
        return CheckResult(app.compose_id, "certs", "fail", item.detail, fix=item.fix)

    @staticmethod
    def _acme_result(app, acme_missing) -> CheckResult:
        item = acme_missing.get(app.name)
        if item is None:
            return CheckResult(
                app.compose_id,
                "certs",
                "ok",
                f"certs/{app.name}/acme.pem+key",
            )
        return CheckResult(app.compose_id, "certs", "fail", item.detail, fix=item.fix)
