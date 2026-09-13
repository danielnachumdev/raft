"""Stack model — applied apps live in ``state/apps/*.yaml`` (on-VPS registry)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Docker Compose project name (containers, networks, tmp names).
COMPOSE_PROJECT = "raft"


@dataclass(frozen=True)
class App:
    """One public site backed by one Compose service name."""

    name: str
    public_host: str
    source: str  # "local" | "git" | "docker"
    path: str  # relative to repo root (git/local); unused for docker without repo
    repo: Optional[str] = None
    ref: str = "main"
    image: Optional[str] = None  # registry/repo without tag (source=docker)

    @property
    def tmp_alias(self) -> str:
        return f"{self.name}_tmp"

    @property
    def tmp_container(self) -> str:
        return f"{COMPOSE_PROJECT}-{self.name}_tmp"

    def abs_path(self, root: Path) -> Path:
        return (root / self.path).resolve()

    def image_ref(self, tag: Optional[str] = None) -> str:
        """Full image reference for pulls: ``repo:tag`` or ``repo@sha256:…``."""
        if not self.image:
            raise ValueError(f"app {self.name!r} has no image (source={self.source})")
        t = (tag if tag is not None else self.ref).strip()
        if not t:
            raise ValueError(f"app {self.name!r}: empty image tag/ref")
        if t.startswith("sha256:"):
            return f"{self.image}@{t}"
        return f"{self.image}:{t}"

    @property
    def compose_pin_image(self) -> str:
        """Image name Compose should pin (default ``ref`` as tag)."""
        return self.image_ref(self.ref)


@dataclass(frozen=True)
class Stack:
    """Gate/router plus apps from the on-VPS apply registry."""

    root: Path
    apps: tuple[App, ...]
    gate: str = "gate"
    router: str = "router"
    public_base_url: str = "http://127.0.0.1"
    state_dir: str = ".deploy"
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
        return self.root / "certs"

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
        return self.root / ".generated"

    def contract_for(self, app: App):
        """Load runtime contract from the applied registry document."""
        from .contract import load_app_file, registry_path

        path = registry_path(self.root, app.name)
        _, contract = load_app_file(path, expect_name=app.name)
        return contract


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Locate the orchestrator checkout (compose.yaml + raft.yaml)."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "compose.yaml").is_file() and (
            candidate / "raft.yaml"
        ).is_file():
            return candidate
    pkg = Path(__file__).resolve().parent
    for candidate in [pkg, *pkg.parents]:
        if (candidate / "compose.yaml").is_file() and (
            candidate / "raft.yaml"
        ).is_file():
            return candidate
    raise FileNotFoundError(
        "could not find orchestrator root (compose.yaml + raft.yaml)"
    )


def load_inventory(root: Path) -> tuple[App, ...]:
    """Compatibility alias: load applied apps from the on-VPS registry."""
    from .contract import load_registry

    return load_registry(root)


def load_stack(root: Optional[Path] = None) -> Stack:
    repo_root = root if root is not None else find_repo_root()
    return Stack(root=repo_root, apps=load_inventory(repo_root))
