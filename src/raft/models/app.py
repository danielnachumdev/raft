"""App model — one Compose service, optionally one public Host."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

COMPOSE_PROJECT = "raft"
# Built-in edge group so gate/router compose ids are raft-gate / raft-router
# (containers raft-raft-gate-1 via project name).
EDGE_GROUP = "raft"


def compose_service_id(name: str, group: Optional[str] = None) -> str:
    """Compose service key (DNS hostname): ``NAME`` or ``GROUP-NAME``.

    Project ``raft`` prefixes containers as ``raft-{service}-N``.
    """
    if group:
        return f"{group}-{name}"
    return name


def display_service_label(compose_id: str, group: Optional[str] = None) -> str:
    """Operator-facing member name when shown under ``group``.

    Compose ids stay ``GROUP-NAME`` for Docker/nginx; UI drops the redundant
    ``GROUP-`` prefix so the heading already names the namespace
    (e.g. ``raft-gate`` → ``gate`` under group ``raft``).
    """
    if group:
        prefix = f"{group}-"
        if compose_id.startswith(prefix):
            return compose_id[len(prefix) :]
    return compose_id


GATE_COMPOSE_ID = compose_service_id("gate", EDGE_GROUP)
ROUTER_COMPOSE_ID = compose_service_id("router", EDGE_GROUP)


@dataclass(frozen=True)
class App:
    name: str
    public_host: str
    source: str
    path: str
    repo: Optional[str] = None
    ref: str = "main"
    image: Optional[str] = None
    # At most one group; drives compose_id. Registry/CLI identity stays ``name``.
    group: Optional[str] = None

    @property
    def compose_id(self) -> str:
        return compose_service_id(self.name, self.group)

    @property
    def tmp_alias(self) -> str:
        return f"{self.compose_id}_tmp"

    @property
    def tmp_container(self) -> str:
        return f"{COMPOSE_PROJECT}-{self.compose_id}_tmp"

    def abs_path(self, root: Path) -> Path:
        return (root / self.path).resolve()

    def image_ref(self, tag: Optional[str] = None) -> str:
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
        return self.image_ref(self.ref)
