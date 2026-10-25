"""Read this process's cgroup / self RSS for controller memory budgets."""

from pathlib import Path
from typing import Optional


class CgroupMemory:
    """Best-effort memory usage ratio for the current process cgroup."""

    def __init__(
        self,
        *,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        proc_self: Path = Path("/proc/self"),
    ) -> None:
        self._cgroup_root = cgroup_root
        self._proc_self = proc_self

    def usage_ratio(self) -> Optional[float]:
        """``current / max`` when both known; else ``None`` (unlimited / missing)."""
        current = self._read_bytes(self._memory_file("memory.current"))
        maximum = self._memory_max()
        if current is None or maximum is None or maximum <= 0:
            return None
        return min(1.0, current / float(maximum))

    def rss_bytes(self) -> Optional[int]:
        """Anonymous RSS from ``/proc/self/status`` (``VmRSS``)."""
        text = self._read_text(self._proc_self / "status")
        if text is None:
            return None
        for line in text.splitlines():
            if not line.startswith("VmRSS:"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
        return None

    def elevated(self, *, threshold: float = 0.75) -> bool:
        """True when cgroup usage is at/above ``threshold`` (default 75%)."""
        ratio = self.usage_ratio()
        return ratio is not None and ratio >= threshold

    def _memory_max(self) -> Optional[int]:
        raw = self._read_text(self._memory_file("memory.max"))
        if raw is None:
            return None
        token = raw.strip()
        if not token or token == "max":
            return None
        if not token.isdigit():
            return None
        return int(token)

    def _memory_file(self, name: str) -> Path:
        # Prefer the process cgroup path when present (container scopes).
        rel = self._cgroup_relative()
        if rel is not None:
            scoped = self._cgroup_root / rel / name
            if scoped.is_file():
                return scoped
        return self._cgroup_root / name

    def _cgroup_relative(self) -> Optional[str]:
        text = self._read_text(self._proc_self / "cgroup")
        if text is None:
            return None
        for line in text.splitlines():
            # cgroup v2: ``0::/system.slice/docker-….scope``
            if "::" not in line:
                continue
            path = line.split("::", 1)[1].strip().lstrip("/")
            return path
        return None

    @staticmethod
    def _read_bytes(path: Path) -> Optional[int]:
        text = CgroupMemory._read_text(path)
        if text is None:
            return None
        token = text.strip()
        if not token.isdigit():
            return None
        return int(token)

    @staticmethod
    def _read_text(path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None
