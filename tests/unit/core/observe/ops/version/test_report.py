"""InstalledVersion formatting for release wheels and git+ installs."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError
from typing import Optional
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.version import InstalledVersion


class TestInstalledVersion:
    def test_line_semver_only_when_no_direct_url(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.11.0"):
            with patch.object(InstalledVersion, "source_detail", return_value=None):
                assert InstalledVersion().line() == "raft 0.11.0"

    def test_line_includes_source_detail(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.1.0"):
            with patch.object(
                InstalledVersion, "source_detail", return_value="git main@398e4ea"
            ):
                assert InstalledVersion().line() == "raft 0.1.0 (git main@398e4ea)"

    def test_package_version_falls_back_to_dunder(self) -> None:
        with patch(
            "raft.core.observe.ops.version.report.version",
            side_effect=PackageNotFoundError("raft"),
        ):
            with patch("raft.__version__", "9.9.9", create=True):
                assert InstalledVersion().package_version() == "9.9.9"

    def test_source_detail_git_ref_and_commit(self) -> None:
        payload = {
            "url": "https://github.com/danielnachumdev/raft.git",
            "vcs_info": {
                "vcs": "git",
                "commit_id": "398e4eaf8c6295db20f57acafb9e81395b03a87f",
                "requested_revision": "main",
            },
        }
        assert self._detail(payload) == "git main@398e4ea"

    def test_source_detail_release_wheel_basename(self) -> None:
        payload = {
            "url": (
                "https://github.com/danielnachumdev/raft/releases/download/"
                "v0.11.0/raft-0.11.0-py3-none-any.whl"
            ),
            "archive_info": {},
        }
        assert self._detail(payload) == "wheel raft-0.11.0-py3-none-any.whl"

    def test_source_detail_editable_path(self) -> None:
        payload = {
            "url": "file:///home/demo/dev/projects/raft",
            "dir_info": {"editable": True},
        }
        assert self._detail(payload) == "editable /home/demo/dev/projects/raft"

    def test_source_detail_none_when_missing(self) -> None:
        with patch.object(InstalledVersion, "_direct_url_text", return_value=None):
            assert InstalledVersion().source_detail() is None

    def test_source_detail_none_on_bad_json(self) -> None:
        with patch.object(InstalledVersion, "_direct_url_text", return_value="{nope"):
            assert InstalledVersion().source_detail() is None

    def test_direct_url_text_reads_distribution(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = '{"url":"x"}'
        with patch(
            "raft.core.observe.ops.version.report.distribution", return_value=dist
        ):
            assert InstalledVersion()._direct_url_text() == '{"url":"x"}'
        dist.read_text.assert_called_once_with("direct_url.json")

    @staticmethod
    def _detail(payload: dict) -> Optional[str]:
        raw = json.dumps(payload)
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            return InstalledVersion().source_detail()
