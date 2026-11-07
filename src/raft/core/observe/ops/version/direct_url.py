"""Parse PEP 610 ``direct_url.json`` into operator-facing install detail."""

import json
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse


class DirectUrl:
    """Read and format ``direct_url.json`` from text or a ``*.dist-info`` dir."""

    def parse(self, raw: Optional[str]) -> Optional[dict[str, Any]]:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    def from_dist_info(self, dist_info: Path) -> Optional[dict[str, Any]]:
        path = dist_info / "direct_url.json"
        if not path.is_file():
            return None
        return self.parse(path.read_text(encoding="utf-8"))

    def detail(self, data: dict[str, Any]) -> Optional[str]:
        vcs = data.get("vcs_info")
        if isinstance(vcs, dict):
            return self.format_git(vcs)
        url = str(data.get("url") or "")
        if url.endswith(".whl"):
            return f"wheel {url.rsplit('/', 1)[-1]}"
        dir_info = data.get("dir_info")
        if isinstance(dir_info, dict):
            return self.format_path(url, editable=bool(dir_info.get("editable")))
        if url.startswith("file:"):
            return self.format_path(url, editable=False)
        return url or None

    def commit(self, data: dict[str, Any]) -> Optional[str]:
        vcs = data.get("vcs_info")
        if not isinstance(vcs, dict):
            return None
        commit = str(vcs.get("commit_id") or "").strip()
        return commit or None

    def repo_url(self, data: dict[str, Any]) -> Optional[str]:
        url = str(data.get("url") or "").strip()
        if not url or url.startswith("file:") or url.endswith(".whl"):
            return None
        return url

    def local_path(self, data: dict[str, Any]) -> Optional[str]:
        if isinstance(data.get("vcs_info"), dict):
            return None
        url = str(data.get("url") or "")
        dir_info = data.get("dir_info")
        if isinstance(dir_info, dict) or url.startswith("file:"):
            path = unquote(urlparse(url).path) if url.startswith("file:") else url
            return path or None
        return None

    @staticmethod
    def format_git(vcs: dict[str, Any]) -> str:
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
    def format_path(url: str, *, editable: bool) -> str:
        path = unquote(urlparse(url).path) if url.startswith("file:") else url
        label = "editable" if editable else "path"
        return f"{label} {path}" if path else label
