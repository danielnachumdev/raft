"""Typed OpsEvent producers for ops-only paths (purge, firewall, alerts, …)."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from .ops_event import OpsEvent
from .ops_event_kinds import (
    KIND_ALERT_FIRED,
    KIND_ALERT_RESOLVED,
    KIND_FIREWALL_APPLY,
    KIND_GATE_RELOAD,
    KIND_STACK_PURGE,
)

logger = logging.getLogger(__name__)


class OpsEventRecords:
    """Mixin: convenience ``record_*`` helpers that call ``append``."""

    def record_purge(
        self,
        *,
        reclaimed_bytes: int,
        image_bytes: int,
        builder_bytes: int,
        ts: Optional[datetime] = None,
    ) -> Optional[OpsEvent]:
        """Purge finished (reclaim summary when known)."""
        return self._safe_record(
            KIND_STACK_PURGE,
            summary=f"Purge reclaimed {reclaimed_bytes}B",
            metadata={
                "reclaimed_bytes": reclaimed_bytes,
                "image_bytes": image_bytes,
                "builder_bytes": builder_bytes,
            },
            ts=ts,
        )

    def record_firewall_apply(
        self, *, rule_count: int, ts: Optional[datetime] = None
    ) -> Optional[OpsEvent]:
        """Ordered firewall document saved → render + gate reload."""
        return self._safe_record(
            KIND_FIREWALL_APPLY,
            summary=f"Firewall applied ({rule_count} rules)",
            metadata={"rule_count": rule_count},
            ts=ts,
        )

    def record_gate_reload(
        self, *, reason: str = "render", ts: Optional[datetime] = None
    ) -> Optional[OpsEvent]:
        """Policy-only gate nginx reload (not recreate)."""
        return self._safe_record(
            KIND_GATE_RELOAD,
            summary="Gate nginx reloaded",
            service="raft-gate",
            metadata={"reason": reason},
            ts=ts,
        )

    def record_alert_fired(
        self,
        *,
        rule_id: str,
        subject: str = "-",
        channel_ids: Optional[Sequence[str]] = None,
        service: Optional[str] = None,
        ts: Optional[datetime] = None,
    ) -> Optional[OpsEvent]:
        """Alert transitioned to firing (no notification body/payload)."""
        return self._alert(
            KIND_ALERT_FIRED,
            rule_id=rule_id,
            subject=subject,
            channel_ids=channel_ids,
            service=service,
            ts=ts,
            verb="fired",
        )

    def record_alert_resolved(
        self,
        *,
        rule_id: str,
        subject: str = "-",
        channel_ids: Optional[Sequence[str]] = None,
        service: Optional[str] = None,
        ts: Optional[datetime] = None,
    ) -> Optional[OpsEvent]:
        """Alert transitioned to resolved."""
        return self._alert(
            KIND_ALERT_RESOLVED,
            rule_id=rule_id,
            subject=subject,
            channel_ids=channel_ids,
            service=service,
            ts=ts,
            verb="resolved",
        )

    def _alert(
        self,
        kind: str,
        *,
        rule_id: str,
        subject: str,
        channel_ids: Optional[Sequence[str]],
        service: Optional[str],
        ts: Optional[datetime],
        verb: str,
    ) -> Optional[OpsEvent]:
        channels = list(channel_ids or ())
        summary = f"Alert {verb} {rule_id}"
        if subject and subject != "-":
            summary = f"{summary} ({subject})"
        meta: Dict[str, Any] = {"rule_id": rule_id, "subject": subject}
        if channels:
            meta["channel_ids"] = channels
        return self._safe_record(
            kind, summary=summary, service=service, metadata=meta, ts=ts
        )

    def _safe_record(
        self,
        kind: str,
        *,
        summary: str,
        metadata: Dict[str, Any],
        ts: Optional[datetime],
        service: Optional[str] = None,
    ) -> Optional[OpsEvent]:
        try:
            return self._record(
                kind, summary=summary, metadata=metadata, ts=ts, service=service
            )
        except OSError:
            logger.warning("ops event record failed kind=%s", kind, exc_info=True)
            return None

    def _record(
        self,
        kind: str,
        *,
        summary: str,
        metadata: Dict[str, Any],
        ts: Optional[datetime],
        service: Optional[str] = None,
    ) -> OpsEvent:
        when = ts or datetime.now(timezone.utc)
        return self.append(
            OpsEvent(
                kind=kind,
                ts=when.isoformat(),
                summary=summary,
                service=service,
                metadata=metadata,
            )
        )
