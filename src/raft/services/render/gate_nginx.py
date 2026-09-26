"""Gate nginx fragment fingerprint + reload stamp."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from ...config.paths import GENERATED_DIRNAME

_GATE_NGINX_SUBDIRS = ("gate-tls", "gate-http", "gate-stream")
GATE_NGINX_RELOAD_STAMP = Path("state") / "gate-nginx.fingerprint"


class GateNginxStamp:
    """Track whether running gate nginx has loaded current on-disk fragments."""

    def __init__(self, stack_root: Path) -> None:
        self.root = stack_root

    def fingerprint(self) -> str:
        """Stable hash of generated gate nginx fragments (tls / http / stream).

        Missing directories count as empty. Does not include ``compose.edge.yaml``
        (published-port changes still require ``raft gate recreate``).
        """
        base = self.root / GENERATED_DIRNAME / "nginx"
        entries = self._collect_entries(base)
        return self._hash_entries(entries)

    def read(self) -> Optional[str]:
        """Fingerprint last successfully loaded into a running gate, if recorded."""
        path = self.root / GATE_NGINX_RELOAD_STAMP
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8").strip()
        return text or None

    def write(self, fingerprint: str) -> None:
        """Record that gate nginx has loaded this fingerprint (reload or cold start)."""
        path = self.root / GATE_NGINX_RELOAD_STAMP
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fingerprint + "\n", encoding="utf-8")

    @staticmethod
    def _collect_entries(base: Path) -> list[tuple[str, bytes]]:
        entries: list[tuple[str, bytes]] = []
        for sub in _GATE_NGINX_SUBDIRS:
            directory = base / sub
            if not directory.is_dir():
                continue
            for path in directory.rglob("*"):
                if path.is_file():
                    rel = f"{sub}/{path.relative_to(directory).as_posix()}"
                    entries.append((rel, path.read_bytes()))
        return entries

    @staticmethod
    def _hash_entries(entries: list[tuple[str, bytes]]) -> str:
        digest = hashlib.sha256()
        for rel, data in sorted(entries, key=lambda item: item[0]):
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
            digest.update(b"\0")
        return digest.hexdigest()
