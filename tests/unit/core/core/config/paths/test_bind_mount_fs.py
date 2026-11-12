"""BindMountFs skips mutative ops on read-only destinations that already exist."""

from __future__ import annotations

import errno
from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.config.paths.bind_mount_fs import BindMountFs


class TestBindMountFs:
    def test_copy_file_skips_identical(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("same\n", encoding="utf-8")
        dest.write_text("same\n", encoding="utf-8")
        with patch("shutil.copy2") as copy2:
            BindMountFs().copy_file(src, dest)
            copy2.assert_not_called()

    def test_copy_file_tolerates_erofs_when_dest_exists(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("new\n", encoding="utf-8")
        dest.write_text("old\n", encoding="utf-8")
        with patch(
            "shutil.copy2",
            side_effect=OSError(errno.EROFS, "Read-only file system"),
        ):
            BindMountFs().copy_file(src, dest)
        assert dest.read_text(encoding="utf-8") == "old\n"

    def test_copy_file_reraises_erofs_when_dest_missing(self, tmp_path: Path) -> None:
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("new\n", encoding="utf-8")
        with patch(
            "shutil.copy2",
            side_effect=OSError(errno.EROFS, "Read-only file system"),
        ):
            with pytest.raises(OSError) as raised:
                BindMountFs().copy_file(src, dest)
        assert raised.value.errno == errno.EROFS

    def test_mkdir_tolerates_erofs_when_dir_exists(self, tmp_path: Path) -> None:
        path = tmp_path / "already"
        path.mkdir()
        with patch.object(
            Path,
            "mkdir",
            side_effect=OSError(errno.EROFS, "Read-only file system"),
        ):
            BindMountFs().mkdir(path)
