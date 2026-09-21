"""Stack model — applied apps live in ``~/.raft/state/apps/*.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from raft.errors import unknown_app

from ..config.paths import (
    CERTS_DIRNAME,
    DEPLOY_DIRNAME,
    GENERATED_DIRNAME,
    ensure_raft_home,
    raft_home,
)
from .app import (
    COMPOSE_PROJECT,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
    App,
)
from .manifest import load_app_file, load_registry, registry_path
from .ports import PortSpec

__all__ = [
    "COMPOSE_PROJECT",
    "GATE_COMPOSE_ID",
    "ROUTER_COMPOSE_ID",
    "App",
    "Stack",
    "load_stack",
]


@dataclass(frozen=True)
class Stack:
    root: Path
    apps: tuple[App, ...]
    gate: str = GATE_COMPOSE_ID
    router: str = ROUTER_COMPOSE_ID
    public_base_url: str = "http://127.0.0.1"
    state_dir: str = DEPLOY_DIRNAME
    drain_seconds: float = 3.0
    ready_timeout_seconds: float = 60.0

    def app(self, name: str) -> App:
        for app in self.apps:
            if app.name == name:
                return app
        known = ", ".join(a.name for a in self.apps) or "(none applied)"
        raise unknown_app(name, known)

    @property
    def core_services(self) -> tuple[str, ...]:
        return (self.gate, self.router, *(app.compose_id for app in self.apps))

    @property
    def upstreams_dir(self) -> Path:
        return self.generated_dir() / "nginx" / "upstreams"

    @property
    def certs_dir(self) -> Path:
        return self.root / CERTS_DIRNAME

    def upstream_file(self, app: App, port: PortSpec) -> Path:
        return self.upstreams_dir / f"{app.name}-{port.name}.conf"

    def upstream_name(self, app: App, port: PortSpec) -> str:
        return f"{app.name}_{port.name}"

    def cert_files(self, app: App) -> tuple[Path, Path]:
        base = self.certs_dir / app.name
        return (base / "origin.pem", base / "origin.key")

    def image_state_file(self, app: App) -> Path:
        return self.root / self.state_dir / f"{app.name}.image"

    def ref_state_file(self, app: App) -> Path:
        return self.root / self.state_dir / f"{app.name}.ref"

    def generated_dir(self) -> Path:
        return self.root / GENERATED_DIRNAME

    def spec_for(self, app: App):
        path = registry_path(self.root, app.name)
        _, app_spec = load_app_file(path, expect_name=app.name)
        return app_spec

    def contract_for(self, app: App):
        return self.spec_for(app)


def load_stack(root: Optional[Path] = None) -> Stack:
    data_home = root if root is not None else raft_home()
    ensure_raft_home(data_home)
    return Stack(root=data_home, apps=load_registry(data_home))
