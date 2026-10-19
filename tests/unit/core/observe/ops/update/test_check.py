"""UpdateCheck against a stub LatestReleaseFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.core.observe.ops.update import LatestRelease, UpdateCheck
from raft.core.observe.ops.version import InstalledVersion


class TestUpdateCheck:
    def test_update_available_when_latest_newer(self) -> None:
        result = self._check("0.10.0", "v0.11.0")
        assert result.update_available is True
        assert result.state == "update_available"
        assert result.latest_version == "0.11.0"
        assert "0.10.0 → 0.11.0" in result.message
        public = result.as_public()
        assert public["updateAvailable"] is True
        assert public["latestTag"] == "v0.11.0"

    def test_up_to_date_when_equal(self) -> None:
        result = self._check("0.11.0", "v0.11.0")
        assert result.update_available is False
        assert result.state == "up_to_date"

    def test_ahead_when_installed_newer(self) -> None:
        result = self._check("0.12.0", "v0.11.0")
        assert result.update_available is False
        assert result.state == "ahead"

    def test_unknown_when_versions_unparsable(self) -> None:
        result = self._check("local-dev", "main-build")
        assert result.state == "unknown"
        assert result.update_available is True

    def test_empty_release_url_becomes_none(self) -> None:
        versions = MagicMock(spec=InstalledVersion)
        versions.package_version.return_value = "0.11.0"
        versions.line.return_value = "raft 0.11.0"
        fetcher = MagicMock()
        fetcher.fetch.return_value = LatestRelease(
            tag="v0.11.0", html_url="", name="v0.11.0"
        )
        result = UpdateCheck(versions=versions, fetcher=fetcher).status()
        assert result.release_url is None

    def _check(self, current: str, tag: str):
        versions = MagicMock(spec=InstalledVersion)
        versions.package_version.return_value = current
        versions.line.return_value = f"raft {current}"
        fetcher = MagicMock()
        fetcher.fetch.return_value = LatestRelease(
            tag=tag,
            html_url="https://github.com/danielnachumdev/raft/releases/tag/" + tag,
            name=tag,
        )
        return UpdateCheck(versions=versions, fetcher=fetcher).status()
