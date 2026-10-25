"""Canonical status snapshot for CLI JSON and serve/FE consumers."""

from typing import Any, Dict, Optional, Tuple

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.status import Status
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.core.observe.ops.version import InstalledVersion
from .depends import ServeDependsMap
from .external_urls import ExternalUrlBuilder
from .snapshot_view import ServeSnapshotView
from .status_resources_overlay import StatusResourcesOverlay


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

    def collect(
        self, *, refresh_apps: bool = False, include_stats: bool = True
    ) -> StatusSnapshot:
        snap = self._status.collect(
            refresh_apps=refresh_apps, include_stats=include_stats
        )
        if refresh_apps:
            self._sync_stack_from_status()
        return snap

    def snapshot_dict(self, *, refresh_apps: bool = False) -> Dict[str, Any]:
        """Machine contract — identical to ``raft status --json`` body."""
        return self.collect(refresh_apps=refresh_apps).to_dict()

    def api_payload(
        self,
        *,
        refresh_apps: bool = False,
        include_stats: bool = True,
        overlay_resources: bool = False,
    ) -> Dict[str, Any]:
        """Serve/FE payload: canonical snapshot + table presentation rows.

        Serve uses ``include_stats=False`` + ``overlay_resources=True`` so the
        hot path skips ``docker stats`` and fills CPU/mem from controller JSONL.
        """
        snap = self.collect(refresh_apps=refresh_apps, include_stats=include_stats)
        resources_as_of = None
        if overlay_resources:
            snap, resources_as_of = self._overlay_resources(snap)
        body = self.payload_from_snapshot(snap)
        if overlay_resources:
            body["resources_as_of"] = resources_as_of
        return body

    def payload_from_snapshot(self, snapshot: StatusSnapshot) -> Dict[str, Any]:
        view = self._view(snapshot).to_payload()
        body = snapshot.to_dict()
        body["control_plane"] = view["control_plane"]
        body["apps"] = view["apps"]
        body["registry_issues"] = [issue.to_dict() for issue in self.stack.registry_issues]
        body["version"] = self._version_payload()
        return body

    def _overlay_resources(
        self, snapshot: StatusSnapshot
    ) -> Tuple[StatusSnapshot, Optional[str]]:
        overlay = StatusResourcesOverlay(self.stack.root)
        return overlay.apply(snapshot), overlay.resources_as_of

    @staticmethod
    def _version_payload() -> Dict[str, str]:
        """Installed raft package version for serve chrome (not CLI ``--json``)."""
        installed = InstalledVersion()
        return {
            "package": installed.package_version(),
            "line": installed.line(),
            "label": installed.chrome_label(),
        }

    def service_detail(self, name: str, *, refresh_apps: bool = False) -> Optional[Dict[str, Any]]:
        """One service's container + presentation row, or None if unknown."""
        return self._view(self.collect(refresh_apps=refresh_apps)).service_detail(name)

    def _sync_stack_from_status(self) -> None:
        """Adopt registry reload from Status (serve out-of-band apply)."""
        reloaded = getattr(self._status, "stack", None)
        if isinstance(reloaded, Stack):
            self.stack = reloaded

    def _view(self, snapshot: StatusSnapshot) -> ServeSnapshotView:
        return ServeSnapshotView(
            snapshot,
            urls=self._url_builder(),
            depends=ServeDependsMap(self.stack),
        )

    def _url_builder(self) -> ExternalUrlBuilder:
        edge = self._edge if self._edge is not None else SettingsLoader().load(self.stack.root).edge
        return ExternalUrlBuilder(self.stack, edge)
