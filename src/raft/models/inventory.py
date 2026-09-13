"""Stack model — applied apps live in ``~/.raft/state/apps/*.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config.paths import (
    CERTS_DIRNAME,
    DEPLOY_DIRNAME,
    GENERATED_DIRNAME,
    ensure_raft_home,
    find_package_root,
    raft_home,
)
from .app import COMPOSE_PROJECT, App
from .contract import load_app_file, load_registry, registry_path

__all__ = [
    "COMPOSE_PROJECT",
    "App",
    "Stack",
    "find_repo_root",
    "load_inventory",
    "load_stack",
]

@dataclass(frozen=True)
class Stack:
    root: Path
    apps: tuple[App, ...]
    gate: str = "gate"
    router: str = "router"
    public_base_url: str = "http://127.0.0.1"
    state_dir: str = DEPLOY_DIRNAME
    drain_seconds: float = 3.0
    ready_timeout_seconds: float = 60.0

    def app(self, name: str) -> App:
        for app in self.apps:
            if app.name == name:
                return app
        known = ", ".join(a.name for a in self.apps) or "(none applied)"
        raise KeyError(f"unknown app {name!r} (known: {known})")

    @property
    def core_services(self) -> tuple[str, ...]:
        return (self.gate, self.router, *(app.name for app in self.apps))

    @property
    def upstreams_dir(self) -> Path:
        return self.generated_dir() / "nginx" / "upstreams"

    @property
    def certs_dir(self) -> Path:
        return self.root / CERTS_DIRNAME

    def upstream_file(self, app: App) -> Path:
        return self.upstreams_dir / f"{app.name}.conf"

    def cert_files(self, app: App) -> tuple[Path, Path]:
        base = self.certs_dir / app.name
        return (base / "origin.pem", base / "origin.key")

    def image_state_file(self, app: App) -> Path:
        return self.root / self.state_dir / f"{app.name}.image"

    def ref_state_file(self, app: App) -> Path:
        return self.root / self.state_dir / f"{app.name}.ref"

    def generated_dir(self) -> Path:
        return self.root / GENERATED_DIRNAME

    def contract_for(self, app: App):
        path = registry_path(self.root, app.name)
        _, contract = load_app_file(path, expect_name=app.name)
        return contract

def find_repo_root(start: Optional[Path] = None) -> Path:
    return find_package_root(start)

def load_inventory(root: Path) -> tuple[App, ...]:
    return load_registry(root)

def load_stack(root: Optional[Path] = None) -> Stack:
    data_home = root if root is not None else raft_home()
    ensure_raft_home(data_home)
    return Stack(root=data_home, apps=load_inventory(data_home))
