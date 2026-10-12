"""Per-app ACME issuance metadata (camelCase JSON keys)."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AcmeAppState:
    """Persisted issuance metadata (camelCase JSON keys)."""

    names: tuple[str, ...] = ()
    not_after: Optional[str] = None
    last_error: Optional[str] = None
    last_success_ts: Optional[float] = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AcmeAppState":
        names_raw = data.get("names") or []
        names = tuple(str(n) for n in names_raw) if isinstance(names_raw, list) else ()
        return cls(
            names=names,
            not_after=cls._opt_str(data.get("notAfter")),
            last_error=cls._opt_str(data.get("lastError")),
            last_success_ts=cls._opt_float(data.get("lastSuccessTs")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "names": list(self.names),
            "notAfter": self.not_after,
            "lastError": self.last_error,
            "lastSuccessTs": self.last_success_ts,
        }

    @staticmethod
    def _opt_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _opt_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)
