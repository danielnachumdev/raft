"""Best-effort git commit/ref from a filesystem checkout (path installs)."""

import subprocess
from pathlib import Path
from typing import Optional


class CheckoutRef:
    """Resolve ``git …@sha`` detail from a still-present working tree."""

    def detail(self, root: Path) -> Optional[str]:
        """Format ``git <ref>@<short>`` when ``root`` is a git checkout."""
        commit = self.commit(root)
        if not commit:
            return None
        short = commit[:7]
        rev = self.ref_name(root)
        if rev and short:
            return f"git {rev}@{short}"
        if short:
            return f"git @{short}"
        return None

    def commit(self, root: Path) -> Optional[str]:
        """Full ``HEAD`` SHA, or None when git is unavailable / not a repo."""
        return self._git_out(root, "rev-parse", "HEAD")

    def ref_name(self, root: Path) -> Optional[str]:
        """Branch name when HEAD is not detached; else None."""
        symbolic = self._git_out(root, "symbolic-ref", "--short", "-q", "HEAD")
        return symbolic or None

    @staticmethod
    def _git_out(root: Path, *args: str) -> Optional[str]:
        if not root.is_dir():
            return None
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        text = (proc.stdout or "").strip()
        return text or None
