"""CheckoutRef resolves git identity from a filesystem tree."""

from pathlib import Path
from unittest.mock import patch

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
