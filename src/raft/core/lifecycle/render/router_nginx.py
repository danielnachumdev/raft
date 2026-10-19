"""Router nginx fragment fingerprint + reload stamp."""

import hashlib
from pathlib import Path
from typing import Optional

from raft.core.core.config.paths import GENERATED_DIRNAME

ROUTER_NGINX_RELOAD_STAMP = Path("state") / "router-nginx.fingerprint"


class RouterNginxStamp:
    """Track whether running router nginx has loaded current Host/upstream files."""

    def __init__(self, stack_root: Path) -> None:
        self.root = stack_root

    def fingerprint(self) -> str:
        """Stable hash of ``router/hosts.conf`` + ``upstreams/*``.

        Missing paths count as empty. Bind-mounted into the router; workers only
        pick up changes after ``nginx -s reload`` (or container recreate).
        """
        base = self.root / GENERATED_DIRNAME / "nginx"
        entries = self._collect_entries(base)
        return self._hash_entries(entries)

    def read(self) -> Optional[str]:
        path = self.root / ROUTER_NGINX_RELOAD_STAMP
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8").strip()
        return text or None

    def write(self, fingerprint: str) -> None:
        path = self.root / ROUTER_NGINX_RELOAD_STAMP
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fingerprint + "\n", encoding="utf-8")

    @staticmethod
    def _collect_entries(base: Path) -> list[tuple[str, bytes]]:
        entries: list[tuple[str, bytes]] = []
        hosts = base / "router" / "hosts.conf"
        if hosts.is_file():
            entries.append(("router/hosts.conf", hosts.read_bytes()))
        upstreams = base / "upstreams"
        if upstreams.is_dir():
            for path in upstreams.rglob("*"):
                if path.is_file():
                    rel = f"upstreams/{path.relative_to(upstreams).as_posix()}"
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
