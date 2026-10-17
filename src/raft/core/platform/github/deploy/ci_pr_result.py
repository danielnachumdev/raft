"""Result DTO for CI workflow PR setup."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CiPrResult:
    status: str
    detail: str
    pr_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": self.status, "detail": self.detail}
        if self.pr_url:
            out["pr_url"] = self.pr_url
        return out
