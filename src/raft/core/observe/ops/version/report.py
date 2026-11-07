"""Human-readable installed raft version (package + optional install source)."""

from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from typing import Optional

from .checkout_ref import CheckoutRef
from .direct_url import DirectUrl
from .source_link import SourceLink
from .stamp import InstallStamp


class InstalledVersion:
    """Format ``raft <semver|git-ref>`` for operators (CLI + serve chrome)."""

    def line(self) -> str:
        """Single-line version string for ``raft --version``."""
        return self._line_from_parts(
            self.package_version(),
            self.source_detail(),
            commit=self.commit_id(),
            repo_url=self.repo_url(),
        )

    def line_for_dist_info(self, dist_info: Path) -> Optional[str]:
        """Format from an on-disk ``*.dist-info`` (uv tool env after reinstall)."""
        pkg = self._version_from_metadata_file(dist_info / "METADATA")
        if not pkg:
            return None
        data = DirectUrl().from_dist_info(dist_info)
        detail = DirectUrl().detail(data) if data else None
        commit = DirectUrl().commit(data) if data else None
        repo = DirectUrl().repo_url(data) if data else None
        return self._line_from_parts(pkg, detail, commit=commit, repo_url=repo)

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

    def source_url(self) -> Optional[str]:
        """GitHub commit URL for non-release installs when a commit SHA is known."""
        return SourceLink().commit_url(self.commit_id(), repo_url=self.repo_url())

    def commit_id(self) -> Optional[str]:
        """Full commit SHA from direct_url, live checkout, or install stamp."""
        data = self._direct_url_data()
        if data:
            from_url = DirectUrl().commit(data)
            if from_url:
                return from_url
            path = DirectUrl().local_path(data)
            if path:
                from_checkout = CheckoutRef().commit(Path(path))
                if from_checkout:
                    return from_checkout
        stamped = InstallStamp().read()
        if stamped and stamped.get("commit"):
            return stamped["commit"]
        return None

    def repo_url(self) -> Optional[str]:
        """Clone / package URL for link building (direct_url or stamp ``repo``)."""
        data = self._direct_url_data()
        if data:
            url = DirectUrl().repo_url(data)
            if url:
                return url
        stamped = InstallStamp().read()
        if stamped and stamped.get("repo"):
            return stamped["repo"]
        return None

    def stamp_fields(self) -> dict[str, str]:
        """Fields written into ``_install_stamp.json`` for this process's identity."""
        package = self.package_version().strip()
        fields: dict[str, str] = {"package": package}
        detail = self.source_detail()
        if detail and detail.strip():
            fields["detail"] = detail.strip()
        commit = self.commit_id()
        if commit and commit.strip():
            fields["commit"] = commit.strip()
        repo = self.repo_url()
        if repo and repo.strip():
            fields["repo"] = repo.strip()
        return fields

    def write_install_stamp(self, package_dir: Path) -> None:
        """Embed this process's install identity into a copied package tree."""
        fields = self.stamp_fields()
        InstallStamp().write(
            package_dir,
            package=fields["package"],
            detail=fields.get("detail"),
            commit=fields.get("commit"),
            repo=fields.get("repo"),
        )

    def source_detail(self) -> Optional[str]:
        """Short install source: prefer git (direct_url / checkout / stamp) over path."""
        data = self._direct_url_data()
        parser = DirectUrl()
        if data and isinstance(data.get("vcs_info"), dict):
            return parser.format_git(data["vcs_info"])
        if data:
            path = parser.local_path(data)
            if path:
                from_checkout = CheckoutRef().detail(Path(path))
                if from_checkout:
                    return from_checkout
        stamped = InstallStamp().read()
        if stamped and stamped.get("detail"):
            return stamped["detail"]
        if data:
            return parser.detail(data)
        return None

    def _package_version_fallback(self) -> str:
        stamped = InstallStamp().read()
        if stamped:
            return stamped["package"]
        from raft import __version__

        return __version__

    @classmethod
    def _line_from_parts(
        cls,
        pkg: str,
        detail: Optional[str],
        *,
        commit: Optional[str] = None,
        repo_url: Optional[str] = None,
    ) -> str:
        if detail and detail.startswith("git "):
            label = detail[4:]
            url = SourceLink().commit_url(commit, repo_url=repo_url)
            if url:
                return f"raft {label} ({url})"
            return f"raft {label}"
        return cls._compose(pkg, detail)

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

    def _direct_url_data(self) -> Optional[dict]:
        return DirectUrl().parse(self._direct_url_text())

    def _detail_from_direct_url_file(self, dist_info: Path) -> Optional[str]:
        data = DirectUrl().from_dist_info(dist_info)
        return DirectUrl().detail(data) if data else None

    def _detail_from_direct_url_text(self, raw: Optional[str]) -> Optional[str]:
        data = DirectUrl().parse(raw)
        return DirectUrl().detail(data) if data else None

    @staticmethod
    def _version_from_metadata_file(path: Path) -> Optional[str]:
        if not path.is_file():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip() or None
        return None

    @staticmethod
    def _format_git(vcs: dict) -> str:
        return DirectUrl.format_git(vcs)
