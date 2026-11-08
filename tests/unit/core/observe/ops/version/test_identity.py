"""InstalledVersion commit / repo / stamp-field identity helpers."""

import json
from pathlib import Path
from unittest.mock import patch

from raft.core.observe.ops.version import InstallStamp, InstalledVersion


_COMMIT = "398e4eaf8c6295db20f57acafb9e81395b03a87f"
_URL = f"https://github.com/danielnachumdev/raft/commit/{_COMMIT}"
_REPO = "https://github.com/danielnachumdev/raft.git"


class TestInstalledVersionIdentity:
    def test_source_url_from_commit(self) -> None:
        with patch.object(InstalledVersion, "commit_id", return_value=_COMMIT):
            with patch.object(InstalledVersion, "repo_url", return_value=None):
                assert InstalledVersion().source_url() == _URL

    def test_commit_id_from_direct_url_vcs(self) -> None:
        raw = json.dumps(
            {"url": _REPO, "vcs_info": {"vcs": "git", "commit_id": _COMMIT}}
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            assert InstalledVersion().commit_id() == _COMMIT

    def test_commit_id_from_checkout_path(self) -> None:
        raw = json.dumps(
            {
                "url": "file:///home/demo/dev/projects/raft",
                "dir_info": {"editable": True},
            }
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            with patch(
                "raft.core.observe.ops.version.report.CheckoutRef.commit",
                return_value=_COMMIT,
            ):
                assert InstalledVersion().commit_id() == _COMMIT

    def test_commit_id_falls_through_when_checkout_misses(self) -> None:
        raw = json.dumps(
            {
                "url": "file:///home/demo/dev/projects/raft",
                "dir_info": {"editable": True},
            }
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            with patch(
                "raft.core.observe.ops.version.report.CheckoutRef.commit",
                return_value=None,
            ):
                with patch(
                    "raft.core.observe.ops.version.report.InstallStamp.read",
                    return_value=None,
                ):
                    assert InstalledVersion().commit_id() is None

    def test_commit_id_falls_through_when_no_local_path(self) -> None:
        raw = json.dumps(
            {
                "url": (
                    "https://github.com/danielnachumdev/raft/releases/download/"
                    "v0.11.0/raft-0.11.0-py3-none-any.whl"
                ),
                "archive_info": {},
            }
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            with patch(
                "raft.core.observe.ops.version.report.InstallStamp.read",
                return_value=None,
            ):
                assert InstalledVersion().commit_id() is None

    def test_commit_id_from_stamp(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(
            pkg, package="0.1.0", detail="git main@398e4ea", commit=_COMMIT
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=None):
            with patch.object(InstallStamp, "_package_dir", return_value=pkg):
                assert InstalledVersion().commit_id() == _COMMIT

    def test_repo_url_from_direct_url(self) -> None:
        raw = json.dumps(
            {"url": _REPO, "vcs_info": {"vcs": "git", "commit_id": _COMMIT}}
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            assert InstalledVersion().repo_url() == _REPO

    def test_repo_url_from_stamp_when_path_install(self, tmp_path: Path) -> None:
        raw = json.dumps({"url": "file:///tmp/raft-install", "dir_info": {}})
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(
            pkg, package="0.1.0", detail="git main@398e4ea", repo=_REPO
        )
        with patch.object(InstalledVersion, "_direct_url_text", return_value=raw):
            with patch.object(InstallStamp, "_package_dir", return_value=pkg):
                assert InstalledVersion().repo_url() == _REPO

    def test_stamp_fields_include_git_identity(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.1.0"):
            with patch.object(
                InstalledVersion, "source_detail", return_value="git main@398e4ea"
            ):
                with patch.object(InstalledVersion, "commit_id", return_value=_COMMIT):
                    with patch.object(
                        InstalledVersion, "repo_url", return_value=_REPO
                    ):
                        assert InstalledVersion().stamp_fields() == {
                            "package": "0.1.0",
                            "detail": "git main@398e4ea",
                            "commit": _COMMIT,
                            "repo": _REPO,
                        }

    def test_stamp_fields_omit_blank_detail(self) -> None:
        with patch.object(InstalledVersion, "package_version", return_value="0.12.7"):
            with patch.object(InstalledVersion, "source_detail", return_value="  "):
                with patch.object(InstalledVersion, "commit_id", return_value=None):
                    with patch.object(InstalledVersion, "repo_url", return_value=None):
                        assert InstalledVersion().stamp_fields() == {
                            "package": "0.12.7"
                        }

    def test_detail_from_direct_url_text(self) -> None:
        raw = json.dumps(
            {
                "url": _REPO,
                "vcs_info": {
                    "vcs": "git",
                    "commit_id": _COMMIT,
                    "requested_revision": "main",
                },
            }
        )
        assert InstalledVersion()._detail_from_direct_url_text(raw) == (
            "git main@398e4ea"
        )
        assert InstalledVersion()._detail_from_direct_url_text(None) is None
