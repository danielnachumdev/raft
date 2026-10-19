"""Fire component: ``raft http_requests …`` (Host-routed request inspection)."""

import json as json_lib
from typing import Any, Dict, Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.observe.read.http_requests import DEFAULT_LIMIT, HttpRequestsRead


class HttpRequestsCLI:
    """List recent gate access.log rows for one Host-routed App.

    Same privacy defaults as serve (no query strings / cookies / Authorization).
    To deny a client IP from a row, use ``raft firewall apply_inspection``.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        reader: Optional[HttpRequestsRead] = None,
    ) -> None:
        self._stack = stack
        self._reader = reader or HttpRequestsRead(stack)

    def show(self, name: str, limit: int = DEFAULT_LIMIT, json: bool = False) -> None:
        """Show recent HTTP requests for a Host-routed App (e.g. ``demo-api``).

        Example::

            raft http_requests show demo-api --limit=50
            raft http_requests show demo-api --json
        """
        payload = self._reader.for_service(name, limit=limit)
        if payload.get("unknown"):
            raise OperatorError(
                f"service {name!r} not found.\nFix: raft get apps",
                has_fix=False,
            )
        if json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=False))
            return
        self._print_human(payload)

    def _print_human(self, payload: Dict[str, Any]) -> None:
        service = payload.get("service") or ""
        if not payload.get("eligible"):
            reason = (payload.get("reason") or "not eligible").strip()
            OperatorSay.say(
                f"{service}: HTTP request inspection unavailable ({reason})."
            )
            return
        rows = list(payload.get("requests") or [])
        self._print_header(payload, service=service, count=len(rows))
        if not rows:
            OperatorSay.say(_empty_history_line(payload))
            return
        OperatorSay.say(
            "TIME  STATUS  METHOD  PATH  CLIENT  LATENCY  UA"
        )
        for row in rows:
            OperatorSay.say(self._row_line(row))

    def _print_header(
        self, payload: Dict[str, Any], *, service: str, count: int
    ) -> None:
        note = _scaled_note(payload)
        OperatorSay.say(
            f"{service}: {count} request(s), limit={payload.get('limit')}{note}"
        )
        OperatorSay.say(
            "Privacy: query strings omitted; cookies/Authorization never logged."
        )
        OperatorSay.say(
            "Firewall a client: "
            "raft firewall apply_inspection --client-ip=192.0.2.10 "
            f"--service={service}"
        )

    @staticmethod
    def _row_line(row: Dict[str, Any]) -> str:
        return (
            f"{row.get('ts') or '-'}  "
            f"{row.get('status') or '-'}  "
            f"{row.get('method') or '-'}  "
            f"{row.get('path') or '-'}  "
            f"{row.get('client_ip') or '-'}  "
            f"{row.get('duration_ms') or '-'}  "
            f"{_short_ua(row.get('user_agent'))}"
        )


def _scaled_note(payload: Dict[str, Any]) -> str:
    if not payload.get("scaled_to_zero"):
        return ""
    return " (scaled to zero — past rows still listed; new traffic will wake the App)"


def _empty_history_line(payload: Dict[str, Any]) -> str:
    if payload.get("scaled_to_zero"):
        return "No retained HTTP requests for this service in the gate access log."
    return "No recent HTTP requests for this service."


def _short_ua(value: Any) -> str:
    text = str(value or "-")
    if len(text) <= 40:
        return text
    return f"{text[:37]}…"
