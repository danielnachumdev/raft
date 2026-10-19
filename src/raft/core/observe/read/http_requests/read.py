"""Recent per-request HTTP rows for Host-routed Apps (serve inspection)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import Stack
from raft.core.core.config.paths.metrics_paths import (
    ACCESS_LOG_NAME,
    GATE_HTTP_LOG_DIR,
)

from .access_parser import (
    DEFAULT_PATH_MAX,
    DEFAULT_UA_MAX,
    HttpAccessLineParser,
    HttpAccessRecord,
)
from .access_tail import AccessLogTail
from .eligibility import HttpRequestsEligibility, HttpRequestsTarget

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MIN_LIMIT = 1


class HttpRequestsRead:
    """Tail gate access.log and return recent rows for one App's Hosts.

    Scaled-to-zero / not-running Apps stay readable when the access log still
    has matching Host rows; ``scaled_to_zero`` is a UI hint only.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        parser: Optional[HttpAccessLineParser] = None,
        eligibility: Optional[HttpRequestsEligibility] = None,
        scaling: Optional[ScalingStore] = None,
        log_path: Optional[Path] = None,
    ) -> None:
        self.stack = stack
        self._parser = parser or HttpAccessLineParser()
        self._eligibility = eligibility or HttpRequestsEligibility(stack)
        self._scaling = scaling or ScalingStore(stack.root)
        self._log_path = log_path or (
            stack.root / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
        )

    def for_service(self, name: str, *, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
        target = self._eligibility.resolve(name)
        capped = self._clamp_limit(limit)
        rows: List[Dict[str, Any]] = []
        if target.eligible:
            rows = self._recent_for_hosts(target.host_set, capped)
        return self._payload(target, capped, rows)

    def bind_stack(self, stack: Stack) -> None:
        """Keep collaborator on the reloaded registry (same as ServePage)."""
        self.stack = stack
        self._eligibility = HttpRequestsEligibility(stack)
        self._scaling = ScalingStore(stack.root)
        self._log_path = stack.root / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME

    def _recent_for_hosts(
        self, hosts: Set[str], limit: int
    ) -> List[Dict[str, Any]]:
        matched: List[HttpAccessRecord] = []
        for line in AccessLogTail(self._log_path).lines():
            record = self._parser.parse(line)
            if record is None or record.host not in hosts:
                continue
            matched.append(record)
        newest = matched[-limit:] if limit else matched
        newest.reverse()
        return [row.to_api_row() for row in newest]

    def _payload(
        self,
        target: HttpRequestsTarget,
        limit: int,
        requests: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        scaled = False
        if target.app is not None:
            scaled = self._scaling.is_scaled_to_zero(target.app.name)
        return {
            "service": target.compose_id,
            "eligible": target.eligible,
            "reason": target.reason,
            "scaled_to_zero": scaled,
            "limit": limit,
            "unknown": target.unknown,
            "privacy": {
                "query_strings": "omitted at source ($uri only)",
                "cookies_authorization_bodies": "never logged",
                "path_max": DEFAULT_PATH_MAX,
                "user_agent_max": DEFAULT_UA_MAX,
            },
            "requests": requests,
        }

    @staticmethod
    def _clamp_limit(limit: int) -> int:
        if limit < MIN_LIMIT:
            return MIN_LIMIT
        if limit > MAX_LIMIT:
            return MAX_LIMIT
        return limit
