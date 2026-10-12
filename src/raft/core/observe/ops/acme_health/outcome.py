"""Result of one ACME cert probe (mapped to CheckResult by CertChecks)."""

from dataclasses import dataclass
from typing import Literal

Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True)
class AcmeHealthOutcome:
    """Result of one ACME cert probe (mapped to CheckResult by CertChecks)."""

    status: Status
    detail: str
    fix: str = ""
