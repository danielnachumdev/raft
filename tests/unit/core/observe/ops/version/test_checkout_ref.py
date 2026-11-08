"""CheckoutRef resolves git identity from a filesystem tree."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.version.checkout_ref import CheckoutRef


class TestCheckoutRef:
    def test_detail_with_branch_and_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch.object(
            CheckoutRef, "commit", return_value="abc1234fffffffff"
        ), patch.object(CheckoutRef, "ref_name", return_value="main"):
            assert CheckoutRef().detail(root) == "git main@abc1234"

    def test_detail_detached_head(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch.object(
            CheckoutRef, "commit", return_value="abc1234fffffffff"
        ), patch.object(CheckoutRef, "ref_name", return_value=None):
            assert CheckoutRef().detail(root) == "git @abc1234"

    def test_detail_none_without_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch.object(CheckoutRef, "commit", return_value=None):
            assert CheckoutRef().detail(root) is None

    def test_git_out_none_when_not_a_dir(self, tmp_path: Path) -> None:
        assert CheckoutRef()._git_out(tmp_path / "missing", "rev-parse", "HEAD") is None

    def test_commit_and_ref_name_via_git_out(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch.object(
            CheckoutRef, "_git_out", side_effect=["deadbeef", "main"]
        ) as git_out:
            assert CheckoutRef().commit(root) == "deadbeef"
            assert CheckoutRef().ref_name(root) == "main"
        assert git_out.call_args_list[0].args[1:] == ("rev-parse", "HEAD")
        assert git_out.call_args_list[1].args[1:] == (
            "symbolic-ref",
            "--short",
            "-q",
            "HEAD",
        )

    def test_git_out_success(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        proc = MagicMock(returncode=0, stdout="abc\n")
        with patch(
            "raft.core.observe.ops.version.checkout_ref.subprocess.run",
            return_value=proc,
        ) as run:
            assert CheckoutRef()._git_out(root, "rev-parse", "HEAD") == "abc"
        run.assert_called_once()

    def test_git_out_nonzero_or_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch(
            "raft.core.observe.ops.version.checkout_ref.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ):
            assert CheckoutRef()._git_out(root, "rev-parse", "HEAD") is None
        with patch(
            "raft.core.observe.ops.version.checkout_ref.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="  \n"),
        ):
            assert CheckoutRef()._git_out(root, "rev-parse", "HEAD") is None

    def test_git_out_oserror_and_timeout(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        with patch(
            "raft.core.observe.ops.version.checkout_ref.subprocess.run",
            side_effect=OSError("no git"),
        ):
            assert CheckoutRef()._git_out(root, "rev-parse", "HEAD") is None
        with patch(
            "raft.core.observe.ops.version.checkout_ref.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            assert CheckoutRef()._git_out(root, "rev-parse", "HEAD") is None
