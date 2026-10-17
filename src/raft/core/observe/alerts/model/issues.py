"""Validation issues and reports for alert rules."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    level: str = "error"


@dataclass
class ValidationReport:
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(ValidationIssue(path, message, "error"))

    def add_warning(self, path: str, message: str) -> None:
        self.warnings.append(ValidationIssue(path, message, "warning"))

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def to_public(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [{"path": i.path, "message": i.message} for i in self.errors],
            "warnings": [
                {"path": i.path, "message": i.message} for i in self.warnings
            ],
        }
