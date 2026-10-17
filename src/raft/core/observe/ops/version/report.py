"""Human-readable installed raft version (package + optional install source)."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, distribution, version
from typing import Any, Optional
from urllib.parse import unquote, urlparse


class InstalledVersion:
    """Format ``raft <semver> [(source)]`` for operators."""

    def line(self) -> str:
        """Single-line version string for ``raft --version``."""
        detail = self.source_detail()
        if detail:
            return f"raft {self.package_version()} ({detail})"
        return f"raft {self.package_version()}"

    def package_version(self) -> str:
        """Packaging version from dist metadata, else ``raft.__version__``."""
        try:
            return version("raft")
        except PackageNotFoundError:
            from raft import __version__

            return __version__

    def source_detail(self) -> Optional[str]:
        """Short install source from ``direct_url.json``, if present."""
        raw = self._direct_url_text()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return self._format_direct_url(data)

    def _direct_url_text(self) -> Optional[str]:
        try:
            dist = distribution("raft")
        except PackageNotFoundError:
            return None
        return dist.read_text("direct_url.json")

    def _format_direct_url(self, data: dict[str, Any]) -> Optional[str]:
        vcs = data.get("vcs_info")
        if isinstance(vcs, dict):
            return self._format_git(vcs)
        url = str(data.get("url") or "")
        if url.endswith(".whl"):
            return f"wheel {url.rsplit('/', 1)[-1]}"
        dir_info = data.get("dir_info")
        if isinstance(dir_info, dict):
            return self._format_path(url, editable=bool(dir_info.get("editable")))
        if url.startswith("file:"):
            return self._format_path(url, editable=False)
        return url or None

    @staticmethod
    def _format_git(vcs: dict[str, Any]) -> str:
        commit = str(vcs.get("commit_id") or "")
        short = commit[:7] if commit else ""
        rev = str(vcs.get("requested_revision") or "").strip()
        if rev and short:
            return f"git {rev}@{short}"
        if rev:
            return f"git {rev}"
        if short:
            return f"git @{short}"
        return "git"

    @staticmethod
    def _format_path(url: str, *, editable: bool) -> str:
        path = unquote(urlparse(url).path) if url.startswith("file:") else url
        label = "editable" if editable else "path"
        return f"{label} {path}" if path else label
