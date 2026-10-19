"""Install stamp for PYTHONPATH Compose images (dashboard/controller)."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from raft.core.observe.ops.version import InstallStamp, InstalledVersion


class TestInstallStamp:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(pkg, package="0.12.7", detail="wheel raft-0.12.7.whl")
        assert InstallStamp().read(pkg) == {
            "package": "0.12.7",
            "detail": "wheel raft-0.12.7.whl",
        }

    def test_write_omits_empty_detail(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(pkg, package="0.12.7", detail=None)
        raw = json.loads((pkg / "_install_stamp.json").read_text(encoding="utf-8"))
        assert raw == {"package": "0.12.7"}

    def test_read_none_when_missing(self, tmp_path: Path) -> None:
        assert InstallStamp().read(tmp_path / "raft") is None

    def test_read_none_on_bad_json(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        (pkg / "_install_stamp.json").write_text("{nope", encoding="utf-8")
        assert InstallStamp().read(pkg) is None

    def test_read_none_without_package_field(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        (pkg / "_install_stamp.json").write_text('{"detail":"x"}\n', encoding="utf-8")
        assert InstallStamp().read(pkg) is None

    def test_read_none_when_json_not_object(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        (pkg / "_install_stamp.json").write_text('["0.12.7"]\n', encoding="utf-8")
        assert InstallStamp().read(pkg) is None


class TestInstalledVersionStampFallback:
    def test_package_version_uses_stamp_without_dist(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(pkg, package="0.12.7", detail=None)
        with patch(
            "raft.core.observe.ops.version.report.version",
            side_effect=PackageNotFoundError("raft"),
        ), patch.object(InstallStamp, "_package_dir", return_value=pkg):
            assert InstalledVersion().package_version() == "0.12.7"

    def test_source_detail_uses_stamp_without_direct_url(self, tmp_path: Path) -> None:
        pkg = tmp_path / "raft"
        pkg.mkdir()
        InstallStamp().write(pkg, package="0.1.0", detail="git main@abc1234")
        with patch.object(
            InstalledVersion, "_direct_url_text", return_value=None
        ), patch.object(InstallStamp, "_package_dir", return_value=pkg):
            assert InstalledVersion().source_detail() == "git main@abc1234"

    def test_chrome_label_prefers_git_detail(self) -> None:
        with patch.object(
            InstalledVersion, "source_detail", return_value="git main@398e4ea"
        ), patch.object(InstalledVersion, "package_version", return_value="0.1.0"):
            assert InstalledVersion().chrome_label() == "main@398e4ea"

    def test_chrome_label_falls_back_to_package(self) -> None:
        with patch.object(
            InstalledVersion, "source_detail", return_value=None
        ), patch.object(InstalledVersion, "package_version", return_value="0.12.7"):
            assert InstalledVersion().chrome_label() == "0.12.7"

    def test_write_install_stamp_from_host_identity(self, tmp_path: Path) -> None:
        dest = tmp_path / "raft"
        dest.mkdir()
        with patch.object(
            InstalledVersion, "package_version", return_value="0.12.7"
        ), patch.object(
            InstalledVersion,
            "source_detail",
            return_value="wheel raft-0.12.7-py3-none-any.whl",
        ):
            InstalledVersion().write_install_stamp(dest)
        assert InstallStamp().read(dest) == {
            "package": "0.12.7",
            "detail": "wheel raft-0.12.7-py3-none-any.whl",
        }
