"""Origin TLS cert presence checks."""

from __future__ import annotations

from raft.errors import OperatorError

from ...certs import missing_origin_certs
from ..context import DoctorContext
from ..models import CheckResult


class CertChecks:
    name = "certs"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        missing_by_name = {m.app_name: m for m in missing_origin_certs(ctx.stack)}
        for app in ctx.stack.apps:
            try:
                app_spec = ctx.stack.spec_for(app)
            except (ValueError, FileNotFoundError, OperatorError):
                continue
            if app_spec.tls != "origin":
                results.append(
                    CheckResult(
                        app.compose_id,
                        "certs",
                        "ok",
                        "n/a (tls: off)",
                    )
                )
                continue
            item = missing_by_name.get(app.name)
            if item is None:
                results.append(
                    CheckResult(
                        app.compose_id,
                        "certs",
                        "ok",
                        f"certs/{app.name}/origin.pem+key",
                    )
                )
                continue
            results.append(
                CheckResult(
                    app.compose_id,
                    "certs",
                    "fail",
                    item.detail,
                    fix=item.fix,
                )
            )
        return results
