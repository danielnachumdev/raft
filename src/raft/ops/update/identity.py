"""Stable identity of the installed raft tool (git commit / dist metadata)."""

import os
import shutil
from pathlib import Path
from typing import Optional


class InstallIdentity:
    """Stable identity of the installed raft tool (git commit / dist metadata)."""

    def read(self) -> Optional[str]:
        """Prefer ``direct_url.json``; fall back to ``METADATA``; else ``None``."""
        tool_root = self._tool_env_root()
        if tool_root is None:
            return None
        dist_infos = sorted(tool_root.glob("lib/python*/site-packages/raft-*.dist-info"))
        if not dist_infos:
            return None
        dist_info = dist_infos[0]
        direct_url = dist_info / "direct_url.json"
        if direct_url.is_file():
            return direct_url.read_text(encoding="utf-8").strip()
        metadata = dist_info / "METADATA"
        if metadata.is_file():
            return metadata.read_text(encoding="utf-8").strip()
        return None

    def _tool_env_root(self) -> Optional[Path]:
        """Locate the uv tool environment that provides ``raft`` on PATH, if any."""
        raft_bin = shutil.which("raft")
        if raft_bin:
            resolved = Path(raft_bin).resolve()
            if resolved.parent.name == "bin":
                return resolved.parent.parent
        tool_dir = os.environ.get("UV_TOOL_DIR")
        root = (
            Path(tool_dir) / "raft"
            if tool_dir
            else Path.home() / ".local" / "share" / "uv" / "tools" / "raft"
        )
        return root if root.is_dir() else None
