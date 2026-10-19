"""Compare installed raft to the latest GitHub Release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from raft.core.observe.ops.version import InstalledVersion
from .latest import LatestRelease, LatestReleaseFetcher
from .semver import SemverParts


@dataclass(frozen=True)
class UpdateCheckResult:
    """Operator-facing check payload for CLI/serve."""

    current: str
    current_line: str
    latest_tag: Optional[str]
    latest_version: Optional[str]
    update_available: bool
    release_url: Optional[str]
    state: str
    message: str

    def as_public(self) -> dict:
        return {
            "current": self.current,
            "currentLine": self.current_line,
            "latestTag": self.latest_tag,
            "latestVersion": self.latest_version,
            "updateAvailable": self.update_available,
            "releaseUrl": self.release_url,
            "state": self.state,
            "message": self.message,
        }


class UpdateCheck:
    """Query GitHub latest Release and compare to ``InstalledVersion``."""

    def __init__(
        self,
        *,
        versions: Optional[InstalledVersion] = None,
        fetcher: Optional[LatestReleaseFetcher] = None,
    ) -> None:
        self._versions = versions or InstalledVersion()
        self._fetcher = fetcher or LatestReleaseFetcher()

    def status(self) -> UpdateCheckResult:
        current = self._versions.package_version()
        line = self._versions.line()
        release = self._fetcher.fetch()
        return self._compare(current, line, release)

    def _compare(
        self, current: str, line: str, release: LatestRelease
    ) -> UpdateCheckResult:
        latest_ver = self._version_label(release.tag)
        cmp = SemverParts.compare(current, latest_ver)
        state, available, message = self._decide(current, release.tag, latest_ver, cmp)
        return self._result(current, line, release, latest_ver, available, state, message)

    @staticmethod
    def _decide(
        current: str, tag: str, latest_ver: str, cmp: Optional[int]
    ) -> tuple:
        if cmp is None:
            return UpdateCheck._unknown(current, tag, latest_ver)
        if cmp < 0:
            msg = f"Update available: {current} → {latest_ver} ({tag})."
            return ("update_available", True, msg)
        if cmp > 0:
            msg = f"Installed {current} is newer than latest Release {tag}."
            return ("ahead", False, msg)
        return ("up_to_date", False, f"raft is up to date ({current}).")

    @staticmethod
    def _unknown(current: str, tag: str, latest_ver: str) -> tuple:
        return (
            "unknown",
            current != latest_ver,
            (
                f"Installed {current}; latest Release is {tag}. "
                "Versions could not be compared automatically."
            ),
        )

    @staticmethod
    def _version_label(tag: str) -> str:
        text = tag.strip()
        if text.lower().startswith("v") and len(text) > 1 and text[1].isdigit():
            return text[1:]
        return text

    @staticmethod
    def _result(
        current: str,
        line: str,
        release: LatestRelease,
        latest_ver: str,
        available: bool,
        state: str,
        message: str,
    ) -> UpdateCheckResult:
        return UpdateCheckResult(
            current=current,
            current_line=line,
            latest_tag=release.tag,
            latest_version=latest_ver,
            update_available=available,
            release_url=release.html_url or None,
            state=state,
            message=message,
        )
