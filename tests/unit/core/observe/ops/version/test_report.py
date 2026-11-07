"""InstalledVersion formatting for release wheels and git+ installs."""

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.version import InstalledVersion


_COMMIT = "398e4eaf8c6295db20f57acafb9e81395b03a87f"
_URL = f"https://github.com/danielnachumdev/raft/commit/{_COMMIT}"


class TestInstalledVersion:
    def test_line_semver_only_when_no_direct_url(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.11.0"):
            with patch.object(InstalledVersion, "source_detail", return_value=None):
                assert InstalledVersion().line() == "raft 0.11.0"

    def test_line_git_prefers_ref_over_packaging_semver(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.1.0"):
            with patch.object(
                InstalledVersion, "source_detail", return_value="git main@398e4ea"
            ):
                with patch.object(InstalledVersion, "commit_id", return_value=_COMMIT):
                    with patch.object(InstalledVersion, "repo_url", return_value=None):
                        assert InstalledVersion().line() == f"raft main@398e4ea ({_URL})"

    def test_line_git_without_commit_omits_url(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.1.0"):
            with patch.object(
                InstalledVersion, "source_detail", return_value="git main@398e4ea"
            ):
                with patch.object(InstalledVersion, "commit_id", return_value=None):
                    assert InstalledVersion().line() == "raft main@398e4ea"

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
        assert InstalledVersion().line_for_dist_info(dist) == (
            "raft feat/foo@def5678 "
            "(https://github.com/danielnachumdev/raft/commit/def5678abcdef)"
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
                "commit_id": _COMMIT,
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
        with patch(
            "raft.core.observe.ops.version.report.CheckoutRef.detail",
            return_value=None,
        ), patch(
            "raft.core.observe.ops.version.report.InstallStamp.read",
            return_value=None,
        ):
            assert self._detail(payload) == "editable /home/demo/dev/projects/raft"

    def test_source_detail_prefers_checkout_git_over_path(self) -> None:
        payload = {
            "url": "file:///home/demo/dev/projects/raft",
            "dir_info": {"editable": True},
        }
        with patch(
            "raft.core.observe.ops.version.report.CheckoutRef.detail",
            return_value="git main@abc1234",
        ):
            assert self._detail(payload) == "git main@abc1234"

    def test_source_detail_prefers_stamp_over_stale_path(self) -> None:
        payload = {
            "url": "file:///tmp/raft-install.gone",
            "dir_info": {},
        }
        with patch(
            "raft.core.observe.ops.version.report.CheckoutRef.detail",
            return_value=None,
        ), patch(
            "raft.core.observe.ops.version.report.InstallStamp.read",
            return_value={
                "package": "0.1.0",
                "detail": "git main@398e4ea",
                "commit": _COMMIT,
            },
        ):
            assert self._detail(payload) == "git main@398e4ea"

    def test_source_detail_none_when_missing(self) -> None:
        with patch.object(InstalledVersion, "_direct_url_text", return_value=None):
            with patch(
                "raft.core.observe.ops.version.report.InstallStamp.read",
                return_value=None,
            ):
                assert InstalledVersion().source_detail() is None

    def test_source_detail_none_on_bad_json(self) -> None:
        with patch.object(InstalledVersion, "_direct_url_text", return_value="{nope"):
            with patch(
                "raft.core.observe.ops.version.report.InstallStamp.read",
                return_value=None,
            ):
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
            with patch(
                "raft.core.observe.ops.version.report.InstallStamp.read",
                return_value=None,
            ):
                assert InstalledVersion().source_detail() is None

    def test_version_from_metadata_none_without_version_field(
        self, tmp_path: Path
    ) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text("Name: raft\n", encoding="utf-8")
        assert InstalledVersion()._version_from_metadata_file(meta) is None

    def test_source_detail_file_url_without_dir_info(self) -> None:
        with patch(
            "raft.core.observe.ops.version.report.CheckoutRef.detail",
            return_value=None,
        ), patch(
            "raft.core.observe.ops.version.report.InstallStamp.read",
            return_value=None,
        ):
            assert self._detail({"url": "file:///opt/raft"}) == "path /opt/raft"

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

    def test_source_url_from_commit(self) -> None:
        with patch.object(InstalledVersion, "commit_id", return_value=_COMMIT):
            with patch.object(InstalledVersion, "repo_url", return_value=None):
                assert InstalledVersion().source_url() == _URL

    @staticmethod
    def _detail(payload: dict) -> Optional[str]:
        raw = json.dumps(payload)
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            return InstalledVersion().source_detail()
