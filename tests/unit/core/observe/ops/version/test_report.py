"""InstalledVersion formatting for release wheels and git+ installs."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
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

    def test_line_for_dist_info_wheel(self, tmp_path: Path) -> None:
        dist = tmp_path / "raft-0.11.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text("Name: raft\nVersion: 0.11.0\n", encoding="utf-8")
        (dist / "direct_url.json").write_text(
            json.dumps(
                {
                    "url": (
                        "https://github.com/danielnachumdev/raft/releases/download/"
                        "v0.11.0/raft-0.11.0-py3-none-any.whl"
                    ),
                    "archive_info": {},
                }
            ),
            encoding="utf-8",
        )
        assert (
            InstalledVersion().line_for_dist_info(dist)
            == "raft 0.11.0 (wheel raft-0.11.0-py3-none-any.whl)"
        )

    def test_line_for_dist_info_git_ref(self, tmp_path: Path) -> None:
        dist = tmp_path / "raft-0.1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text("Name: raft\nVersion: 0.1.0\n", encoding="utf-8")
        (dist / "direct_url.json").write_text(
            json.dumps(
                {
                    "url": "https://github.com/danielnachumdev/raft.git",
                    "vcs_info": {
                        "vcs": "git",
                        "commit_id": "def5678abcdef",
                        "requested_revision": "feat/foo",
                    },
                }
            ),
            encoding="utf-8",
        )
        assert (
            InstalledVersion().line_for_dist_info(dist)
            == "raft 0.1.0 (git feat/foo@def5678)"
        )

    def test_line_for_dist_info_none_without_metadata(self, tmp_path: Path) -> None:
        dist = tmp_path / "raft-0.1.0.dist-info"
        dist.mkdir()
        assert InstalledVersion().line_for_dist_info(dist) is None

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

    def test_direct_url_text_none_when_package_missing(self) -> None:
        with patch(
            "raft.core.observe.ops.version.report.distribution",
            side_effect=PackageNotFoundError("raft"),
        ):
            assert InstalledVersion()._direct_url_text() is None

    def test_detail_from_direct_url_file_none_when_missing(
        self, tmp_path: Path
    ) -> None:
        dist = tmp_path / "raft-0.1.0.dist-info"
        dist.mkdir()
        assert InstalledVersion()._detail_from_direct_url_file(dist) is None

    def test_source_detail_none_when_json_not_object(self) -> None:
        with patch.object(InstalledVersion, "_direct_url_text", return_value="[]"):
            assert InstalledVersion().source_detail() is None

    def test_version_from_metadata_none_without_version_field(
        self, tmp_path: Path
    ) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text("Name: raft\n", encoding="utf-8")
        assert InstalledVersion()._version_from_metadata_file(meta) is None

    def test_source_detail_file_url_without_dir_info(self) -> None:
        assert (
            self._detail({"url": "file:///opt/raft"}) == "path /opt/raft"
        )

    def test_source_detail_plain_url_fallback(self) -> None:
        assert self._detail({"url": "https://example.test/raft"}) == (
            "https://example.test/raft"
        )

    def test_source_detail_empty_url_none(self) -> None:
        assert self._detail({"url": ""}) is None

    def test_format_git_rev_only(self) -> None:
        assert InstalledVersion()._format_git({"requested_revision": "main"}) == (
            "git main"
        )

    def test_format_git_commit_only(self) -> None:
        assert InstalledVersion()._format_git({"commit_id": "abc1234xxxx"}) == (
            "git @abc1234"
        )

    def test_format_git_bare(self) -> None:
        assert InstalledVersion()._format_git({}) == "git"

    @staticmethod
    def _detail(payload: dict) -> Optional[str]:
        raw = json.dumps(payload)
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            return InstalledVersion().source_detail()
