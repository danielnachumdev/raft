"""Human-readable installed raft version (package + optional install source)."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from .stamp import InstallStamp


class InstalledVersion:
    """Format ``raft <semver> [(source)]`` for operators."""

    def line(self) -> str:
        """Single-line version string for ``raft --version``."""
        return self._compose(self.package_version(), self.source_detail())

    def line_for_dist_info(self, dist_info: Path) -> Optional[str]:
        """Format from an on-disk ``*.dist-info`` (uv tool env after reinstall)."""
        pkg = self._version_from_metadata_file(dist_info / "METADATA")
        if not pkg:
            return None
        return self._compose(pkg, self._detail_from_direct_url_file(dist_info))

    def package_version(self) -> str:
        """Packaging version from dist metadata, install stamp, or ``__version__``."""
        try:
            return version("raft")
        except PackageNotFoundError:
            return self._package_version_fallback()

    def chrome_label(self) -> str:
        """Short UI label: git ``rev@sha`` when that is the install SoT, else semver."""
        detail = self.source_detail()
        if detail and detail.startswith("git "):
            return detail[4:]
        return self.package_version()

    def write_install_stamp(self, package_dir: Path) -> None:
        """Embed this process's install identity into a copied package tree."""
        InstallStamp().write(
            package_dir,
            package=self.package_version(),
            detail=self.source_detail(),
        )

    def source_detail(self) -> Optional[str]:
        """Short install source from ``direct_url.json`` or image install stamp."""
        from_url = self._detail_from_direct_url_text(self._direct_url_text())
        if from_url is not None:
            return from_url
        stamped = InstallStamp().read()
        return stamped.get("detail") if stamped else None

    def _package_version_fallback(self) -> str:
        stamped = InstallStamp().read()
        if stamped:
            return stamped["package"]
        from raft import __version__

        return __version__

    @staticmethod
    def _compose(pkg: str, detail: Optional[str]) -> str:
        if detail:
            return f"raft {pkg} ({detail})"
        return f"raft {pkg}"

    def _direct_url_text(self) -> Optional[str]:
        try:
            dist = distribution("raft")
        except PackageNotFoundError:
            return None
        return dist.read_text("direct_url.json")

    def _detail_from_direct_url_file(self, dist_info: Path) -> Optional[str]:
        path = dist_info / "direct_url.json"
        if not path.is_file():
            return None
        return self._detail_from_direct_url_text(path.read_text(encoding="utf-8"))

    def _detail_from_direct_url_text(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return self._format_direct_url(data)

    @staticmethod
    def _version_from_metadata_file(path: Path) -> Optional[str]:
        if not path.is_file():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip() or None
        return None

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
