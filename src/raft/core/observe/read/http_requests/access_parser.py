"""Parse gate ``raft_http`` access-log lines (legacy + enriched)."""

import re
from dataclasses import dataclass
from typing import Match, Optional, Tuple

_ENRICHED = re.compile(
    r"^(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\"(.*)\"\s*$"
)
_LEGACY = re.compile(r"^(\S+)\s+(\d+)\s+(\S+)\s*$")

DEFAULT_PATH_MAX = 256
DEFAULT_UA_MAX = 160


@dataclass(frozen=True)
class HttpAccessRecord:
    """One gate HTTP access row for serve inspection (or metrics scrape)."""

    duration_s: float
    status: int
    host: str
    ts: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    enriched: bool = False

    @property
    def duration_ms(self) -> float:
        return round(self.duration_s * 1000.0, 3)

    def to_api_row(self) -> dict:
        return {
            "ts": self.ts,
            "method": self.method,
            "path": self.path,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "client_ip": self.client_ip,
            "host": self.host,
            "user_agent": self.user_agent,
            "enriched": self.enriched,
        }


class HttpAccessLineParser:
    """Parse space-separated ``raft_http`` lines; redact long path/UA."""

    def __init__(
        self,
        *,
        path_max: int = DEFAULT_PATH_MAX,
        ua_max: int = DEFAULT_UA_MAX,
    ) -> None:
        self._path_max = path_max
        self._ua_max = ua_max

    def parse(self, raw: str) -> Optional[HttpAccessRecord]:
        text = raw.strip()
        if not text:
            return None
        enriched = _ENRICHED.match(text)
        if enriched:
            return self._from_enriched(enriched)
        legacy = _LEGACY.match(text)
        if legacy:
            return self._from_legacy(legacy)
        return None

    def _from_enriched(self, match: Match) -> Optional[HttpAccessRecord]:
        duration_s, status = self._duration_status(match.group(1), match.group(2))
        if duration_s is None or status is None:
            return None
        host = match.group(3).lower()
        if not host or host == "-":
            return None
        return HttpAccessRecord(
            duration_s=duration_s,
            status=status,
            host=host,
            ts=match.group(4),
            method=match.group(5),
            path=self._clip(match.group(6), self._path_max),
            client_ip=match.group(7),
            user_agent=self._clip(match.group(8), self._ua_max),
            enriched=True,
        )

    def _from_legacy(self, match: Match) -> Optional[HttpAccessRecord]:
        duration_s, status = self._duration_status(match.group(1), match.group(2))
        if duration_s is None or status is None:
            return None
        host = match.group(3).lower()
        if not host or host == "-":
            return None
        return HttpAccessRecord(duration_s=duration_s, status=status, host=host)

    @staticmethod
    def _duration_status(
        duration_raw: str, status_raw: str
    ) -> Tuple[Optional[float], Optional[int]]:
        try:
            return float(duration_raw), int(status_raw)
        except ValueError:
            return None, None

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 1)] + "…"
