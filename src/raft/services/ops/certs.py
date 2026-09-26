"""Origin TLS cert presence checks shared by doctor and deploy/render paths."""

from __future__ import annotations

from dataclasses import dataclass

from raft.errors import (
    format_missing_origin_certs,
    looks_like_missing_origin_cert,
)
from raft.errors.cta import OperatorError

from ...models.stack import Stack


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


def missing_origin_certs(stack: Stack) -> list[MissingOriginCerts]:
    """Return missing PEM/key pairs for every applied app with ``tls: origin``."""
    results: list[MissingOriginCerts] = []
    for app in stack.apps:
        try:
            app_spec = stack.spec_for(app)
        except (ValueError, FileNotFoundError, OperatorError):
            continue
        if app_spec.tls != "origin":
            continue
        pem, key = stack.cert_files(app)
        missing = tuple(p.name for p in (pem, key) if not p.is_file())
        if missing:
            results.append(MissingOriginCerts(app.name, missing))
    return results


def require_origin_certs(stack: Stack) -> None:
    """Raise if any ``tls: origin`` app is missing PEMs (before gate nginx load)."""
    missing = missing_origin_certs(stack)
    if not missing:
        return
    raise OperatorError(
        format_missing_origin_certs(missing, include_doctor_footer=True)
    )
