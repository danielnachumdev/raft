"""Stack model — applied apps live in ``~/.raft/services/<name>/app.yaml``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from raft.core.core.config.paths import (
    GENERATED_DIRNAME,
    RaftHome,
    RaftHomeBootstrap,
    ServicePaths,
)
from raft.core.core.errors.domain import DomainErrors
from .app import (
    COMPOSE_PROJECT,
    CONTROLLER_COMPOSE_ID,
    DASHBOARD_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
    App,
)
from .app_document import AppDocument
from .ports import PortSpec
from .registry import AppRegistry
from .registry_issue import RegistryIssue

__all__ = [
    "COMPOSE_PROJECT",
    "CONTROLLER_COMPOSE_ID",
    "GATE_COMPOSE_ID",
    "ROUTER_COMPOSE_ID",
    "App",
    "RegistryIssue",
    "Stack",
    "load_stack",
]


@dataclass(frozen=True)
class Stack:
    root: Path
    apps: tuple[App, ...]
    registry_issues: tuple[RegistryIssue, ...] = ()
    gate: str = GATE_COMPOSE_ID
    router: str = ROUTER_COMPOSE_ID
    controller: str = CONTROLLER_COMPOSE_ID
    dashboard: str = DASHBOARD_COMPOSE_ID
    public_base_url: str = "http://127.0.0.1"
    drain_seconds: float = 3.0
    # Fallback only; App ``spec.readiness.timeoutSeconds`` (default 120s) wins.
    ready_timeout_seconds: float = 120.0

    def app(self, name: str) -> App:
        for app in self.apps:
            if app.name == name:
                return app
        known = ", ".join(a.name for a in self.apps) or "(none applied)"
        raise DomainErrors.unknown_app(name, known)

    @property
    def control_plane_services(self) -> tuple[str, ...]:
        """Gate, optional dashboard, router, controller — no Apps.

        Order matches selective ``raft up`` so Compose DNS for dashboard
        exists before the router starts.
        """
        edge = [self.gate]
        if self._dashboard_enabled():
            edge.append(self.dashboard)
        edge.extend((self.router, self.controller))
        return tuple(edge)

    @property
    def core_services(self) -> tuple[str, ...]:
        return self.control_plane_services + tuple(
            app.compose_id for app in self.apps
        )

    def _dashboard_enabled(self) -> bool:
        try:
            from raft.core.core.config.settings import SettingsLoader

            return SettingsLoader().load(self.root).dashboard.enabled
        except Exception:  # noqa: BLE001 — status/doctor tolerate bad settings
            return False

    @property
    def upstreams_dir(self) -> Path:
        return self.generated_dir() / "nginx" / "upstreams"

    def certs_dir(self, app: App) -> Path:
        return ServicePaths(self.root, app.name).certs()

    def upstream_file(self, app: App, port: PortSpec) -> Path:
        return self.upstreams_dir / f"{app.name}-{port.name}.conf"

    def upstream_name(self, app: App, port: PortSpec) -> str:
        return f"{app.name}_{port.name}"

    def cert_files(self, app: App) -> tuple[Path, Path]:
        base = self.certs_dir(app)
        return (base / "origin.pem", base / "origin.key")

    def image_state_file(self, app: App) -> Path:
        return ServicePaths(self.root, app.name).deploy_image()

    def ref_state_file(self, app: App) -> Path:
        return ServicePaths(self.root, app.name).deploy_ref()

    def generated_dir(self) -> Path:
        return self.root / GENERATED_DIRNAME

    def spec_for(self, app: App):
        path = AppRegistry(self.root).path_for(app.name)
        _, app_spec = AppDocument.load(path, expect_name=app.name)
        return app_spec

    def contract_for(self, app: App):
        return self.spec_for(app)

    @classmethod
    def load_apps(cls, root: Path) -> "Stack":
        """Load applied apps without mutating the data home.

        Controllers use this when ``~/.raft`` is mounted read-only (no
        ``ensure_raft_home``). Operator CLI paths should prefer ``load_stack``.
        Invalid registry YAML is skipped (see ``registry_issues``); apply/write
        still rejects bad manifests with a clear error.
        """
        result = AppRegistry(root).load_result()
        return cls(root=root, apps=result.apps, registry_issues=result.issues)


def load_stack(root: Optional[Path] = None) -> Stack:
    data_home = root if root is not None else RaftHome().resolve()
    RaftHomeBootstrap().ensure(data_home)
    return Stack.load_apps(data_home)
