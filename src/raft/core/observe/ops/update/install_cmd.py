"""Shared ``install.sh`` bash pipeline for in-process and host Docker apply."""

from __future__ import annotations

import shlex
from typing import Optional

from raft.core.platform.adapters.docker import DEFAULT_HOST_ONESHOT_IMAGE

DEFAULT_INSTALL_URL = (
    "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"
)

# Re-export: Settings → Update and HostOneshot share the same default image.
DEFAULT_HOST_UPDATE_IMAGE = DEFAULT_HOST_ONESHOT_IMAGE


class InstallCmd:
    """Build the quiet ``curl | bash`` installer argv / script body."""

    @classmethod
    def in_process_argv(cls, url: str, ref: Optional[str]) -> list[str]:
        """``bash -c`` argv for host ``raft update`` / non-dashboard serve."""
        return ["bash", "-c", cls.pipeline_script(ref), "_", url]

    @classmethod
    def pipeline_script(cls, ref: Optional[str]) -> str:
        """``pipefail`` required so a missing ``curl`` cannot exit 0."""
        return f"set -euo pipefail; {cls._exports(ref)}; curl -fsSL \"$1\" | bash"

    @staticmethod
    def _exports(ref: Optional[str]) -> str:
        export = "export RAFT_INSTALL_QUIET=1"
        cleaned = (ref or "").strip()
        if cleaned:
            export = f"{export}; export RAFT_REF={shlex.quote(cleaned)}"
        return export
