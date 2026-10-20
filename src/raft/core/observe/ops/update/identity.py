"""Stable identity of the installed raft tool (git commit / dist metadata)."""

import os
import shutil
from pathlib import Path
from typing import Optional


class InstallIdentity:
    """Stable identity of the installed raft tool (git commit / dist metadata)."""

    def dist_info_dir(self) -> Optional[Path]:
        """Path to the active ``raft-*.dist-info`` under the uv tool env, if any."""
        tool_root = self._tool_env_root()
        if tool_root is None:
            return None
        dist_infos = sorted(tool_root.glob("lib/python*/site-packages/raft-*.dist-info"))
        return dist_infos[0] if dist_infos else None

    def read(self) -> Optional[str]:
        """Prefer ``direct_url.json``; fall back to ``METADATA``; else ``None``."""
        dist_info = self.dist_info_dir()
        if dist_info is None:
            return None
        direct_url = dist_info / "direct_url.json"
        if direct_url.is_file():
            return direct_url.read_text(encoding="utf-8").strip()
        metadata = dist_info / "METADATA"
        if metadata.is_file():
            return metadata.read_text(encoding="utf-8").strip()
        return None

    def _tool_env_root(self) -> Optional[Path]:
        """Locate the uv tool environment that provides ``raft`` on PATH, if any."""
        from_bin = self._root_from_raft_bin()
        if from_bin is not None:
            return from_bin
        for root in self._candidate_roots():
            if root.is_dir():
                return root
        return None

    @staticmethod
    def _root_from_raft_bin() -> Optional[Path]:
        raft_bin = shutil.which("raft")
        if not raft_bin:
            return None
        resolved = Path(raft_bin).resolve()
        if resolved.parent.name == "bin":
            return resolved.parent.parent
        return None

    @staticmethod
    def _candidate_roots() -> list[Path]:
        roots: list[Path] = []
        host_home = (os.environ.get("RAFT_HOST_HOME") or "").strip()
        if host_home:
            roots.append(Path(host_home) / ".local" / "share" / "uv" / "tools" / "raft")
        tool_dir = os.environ.get("UV_TOOL_DIR")
        if tool_dir:
            roots.append(Path(tool_dir) / "raft")
        else:
            roots.append(Path.home() / ".local" / "share" / "uv" / "tools" / "raft")
        return roots
