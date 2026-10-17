"""Fire component: ``raft events`` (ops timeline over ``state/events/ops.jsonl``)."""

import json as json_lib
from typing import Optional

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.observe.ops.events import OpsEventsService
from raft.core.observe.ops.events.service import DEFAULT_HOURS, DEFAULT_LIMIT


class EventsCLI:
    """List the durable operator system event journal (#267)."""

    def __init__(
        self, stack: Stack, *, service: Optional[OpsEventsService] = None
    ) -> None:
        self._stack = stack
        self._service = service or OpsEventsService(stack.root)

    def __call__(
        self,
        hours: int = DEFAULT_HOURS,
        service: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        json: bool = False,
    ) -> None:
        """Print recent ops events (same journal as serve Events).

        Example::

            raft events --hours=6 --service=demo-api
            raft events --kind=alert.fired --json
        """
        payload = self._service.list_events(
            hours=hours, service=service, kind=kind, limit=limit
        )
        if json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=False))
            return
        self._print_table(payload)

    @staticmethod
    def _print_table(payload) -> None:
        events = payload.get("events") or []
        OperatorSay.say(
            f"events: last {payload.get('hours')}h "
            f"({payload.get('count')} shown)"
        )
        if not events:
            OperatorSay.say("  (none)")
            return
        for row in events:
            svc = row.get("service") or "-"
            OperatorSay.say(
                f"  {row.get('ts')}  {row.get('kind'):<20}  "
                f"{svc:<16}  {row.get('summary')}"
            )
