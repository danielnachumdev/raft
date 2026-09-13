"""App model — one public site backed by one Compose service name."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

COMPOSE_PROJECT = "raft"

@dataclass(frozen=True)
class App:
    name: str
    public_host: str
    source: str
    path: str
    repo: Optional[str] = None
    ref: str = "main"
    image: Optional[str] = None

    @property
    def tmp_alias(self) -> str:
        return f"{self.name}_tmp"

    @property
    def tmp_container(self) -> str:
        return f"{COMPOSE_PROJECT}-{self.name}_tmp"

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
