"""Origin TLS cert presence checks."""

from __future__ import annotations

from typing import Optional

from raft.errors import OperatorError

from ...certs import missing_origin_certs
from ..context import DoctorContext
from ..models import CheckResult


class CertChecks:
    name = "certs"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        missing_by_name = {m.app_name: m for m in missing_origin_certs(ctx.stack)}
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            result = self._check_app(ctx, app, missing_by_name)
            if result is not None:
                results.append(result)
        return results

    def _check_app(self, ctx: DoctorContext, app, missing_by_name) -> Optional[CheckResult]:
        try:
            app_spec = ctx.stack.spec_for(app)
        except (ValueError, FileNotFoundError, OperatorError):
            return None
        if app_spec.tls != "origin":
            return CheckResult(app.compose_id, "certs", "ok", "n/a (tls: off)")
        item = missing_by_name.get(app.name)
        if item is None:
            return CheckResult(
                app.compose_id,
                "certs",
                "ok",
                f"certs/{app.name}/origin.pem+key",
            )
        return CheckResult(app.compose_id, "certs", "fail", item.detail, fix=item.fix)
