"""Canonical status snapshot for CLI JSON and serve/FE consumers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...config.settings import load_config
from ...config.settings_types import EdgeConfig
from ...models import Stack
from ..ops.status import Status
from ..ops.status.models import StatusSnapshot
from .depends import ServeDependsMap
from .external_urls import ExternalUrlBuilder
from .view import ServeSnapshotView


class StatusRead:
    """One collector path for ``raft status`` and ``raft serve`` /api/status."""

    def __init__(
        self,
        stack: Stack,
        status: Optional[Status] = None,
        *,
        edge: Optional[EdgeConfig] = None,
    ) -> None:
        self.stack = stack
        self._status = status if status is not None else Status(stack)
        self._edge = edge

    @property
    def status(self) -> Status:
        return self._status

    def collect(self, *, refresh_apps: bool = False) -> StatusSnapshot:
        return self._status.collect(refresh_apps=refresh_apps)

    def snapshot_dict(self, *, refresh_apps: bool = False) -> Dict[str, Any]:
        """Machine contract — identical to ``raft status --json`` body."""
        return self.collect(refresh_apps=refresh_apps).to_dict()

    def api_payload(self, *, refresh_apps: bool = False) -> Dict[str, Any]:
        """Serve/FE payload: canonical snapshot + table presentation rows."""
        return self.payload_from_snapshot(self.collect(refresh_apps=refresh_apps))

    def payload_from_snapshot(self, snapshot: StatusSnapshot) -> Dict[str, Any]:
        view = self._view(snapshot).to_payload()
        body = snapshot.to_dict()
        body["control_plane"] = view["control_plane"]
        body["apps"] = view["apps"]
        return body

    def service_detail(self, name: str, *, refresh_apps: bool = False) -> Optional[Dict[str, Any]]:
        """One service's container + presentation row, or None if unknown."""
        return self._view(self.collect(refresh_apps=refresh_apps)).service_detail(name)

    def _view(self, snapshot: StatusSnapshot) -> ServeSnapshotView:
        return ServeSnapshotView(
            snapshot,
            urls=self._url_builder(),
            depends=ServeDependsMap(self.stack),
        )

    def _url_builder(self) -> ExternalUrlBuilder:
        edge = self._edge if self._edge is not None else load_config(self.stack.root).edge
        return ExternalUrlBuilder(self.stack, edge)
