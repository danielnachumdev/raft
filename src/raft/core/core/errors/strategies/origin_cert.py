"""Classify missing Origin TLS certificate failures."""

import subprocess

from ..certs_msgs import CertMessages
from ..classify_ctx import SubprocessCtx
from ..cmd_parts import CmdParts
from ..operator_error import OperatorError
from .rule import SubprocessRule


class OriginCertRule(SubprocessRule):
    name = "origin_cert"

    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        return CertMessages.looks_like_missing_origin_cert(CmdParts.blob(exc, detail))

    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        del exc
        missing = list(ctx.missing_certs or ())
        if missing:
            return OperatorError(
                CertMessages.format_missing_origin_certs(missing, include_doctor_footer=False)
            )
        return OperatorError(CertMessages.missing_origin_certs_fallback(detail=detail))
