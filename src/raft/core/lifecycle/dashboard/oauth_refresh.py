"""Reload dashboard edge so oauth2-proxy re-reads derived allowlist."""

from typing import Any, Dict

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.actions import ServiceActions


class OAuthAllowlistRefresh:
    """Best-effort ``raft redeploy dashboard`` (oneshot when inside dashboard)."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def after_sync(self, sync_result: Dict[str, Any]) -> Dict[str, Any]:
        if not sync_result.get("synced"):
            return {"refreshed": False, "reason": "allowlist not synced"}
        try:
            payload = ServiceActions(self._stack).redeploy(self._stack.dashboard)
        except OperatorError as exc:
            return {
                "refreshed": False,
                "reason": str(exc),
                "note": (
                    "Allowlist was written; run `raft redeploy dashboard` "
                    "so oauth2-proxy reloads it."
                ),
            }
        return {"refreshed": True, "redeploy": payload}
