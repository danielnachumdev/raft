"""Compare installed raft to the latest GitHub Release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from raft.core.observe.ops.version import InstalledVersion
from .host_apply import HostApplyGate
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
    can_apply: bool = True
    apply_block_reason: Optional[str] = None

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
            "canApply": self.can_apply,
            "applyBlockReason": self.apply_block_reason,
        }


class UpdateCheck:
    """Query GitHub latest Release and compare to ``InstalledVersion``."""

    def __init__(
        self,
        *,
        versions: Optional[InstalledVersion] = None,
        fetcher: Optional[LatestReleaseFetcher] = None,
        host_gate: Optional[HostApplyGate] = None,
    ) -> None:
        self._versions = versions or InstalledVersion()
        self._fetcher = fetcher or LatestReleaseFetcher()
        self._host_gate = host_gate or HostApplyGate()

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

    def _result(
        self,
        current: str,
        line: str,
        release: LatestRelease,
        latest_ver: str,
        available: bool,
        state: str,
        message: str,
    ) -> UpdateCheckResult:
        block = self._host_gate.blocked_reason()
        can_apply = block is None
        return UpdateCheckResult(
            current=current,
            current_line=line,
            latest_tag=release.tag,
            latest_version=latest_ver,
            update_available=available,
            release_url=release.html_url or None,
            state=state,
            message=self._message_with_block(message, block),
            can_apply=can_apply,
            apply_block_reason=block,
        )

    @staticmethod
    def _message_with_block(message: str, block: Optional[str]) -> str:
        if not block:
            return message
        first = block.split("\n", 1)[0].rstrip(".")
        return f"{message} {first}."
