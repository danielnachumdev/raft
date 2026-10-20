"""Shared ``install.sh`` bash pipeline for in-process and host Docker apply."""

from __future__ import annotations

import shlex
from typing import Optional

DEFAULT_INSTALL_URL = (
    "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"
)

# curl + bash + git (install.sh always calls ensure_git); override with
# ``RAFT_HOST_UPDATE_IMAGE``. bookworm-curl lacks git and fails apply.
DEFAULT_HOST_UPDATE_IMAGE = "docker.io/library/buildpack-deps:bookworm-scm"


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
