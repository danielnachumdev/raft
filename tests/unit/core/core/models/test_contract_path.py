"""ContractRelPath normalization (dummy paths only)."""

from pathlib import Path

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.contract_path import ContractRelPath


class TestContractRelPath:
    def test_default_and_normalize(self) -> None:
        paths = ContractRelPath()
        assert paths.normalize("") == ".raft/app.yaml"
        assert paths.normalize("  apps/demo/.raft/app.yaml  ") == (
            "apps/demo/.raft/app.yaml"
        )
        assert paths.normalize(r"apps\demo\app.yaml") == "apps/demo/app.yaml"

    def test_rejects_absolute_and_parent(self) -> None:
        paths = ContractRelPath()
        with pytest.raises(OperatorError, match="relative"):
            paths.normalize("/tmp/app.yaml")
        with pytest.raises(OperatorError, match="relative"):
            paths.normalize("../app.yaml")
        with pytest.raises(OperatorError, match="file"):
            paths.normalize("apps/demo/")

    def test_under_stays_in_root(self, tmp_path: Path) -> None:
        paths = ContractRelPath()
        root = tmp_path / "repo"
        root.mkdir()
        target = root / "nested" / "app.yaml"
        target.parent.mkdir()
        target.write_text("x", encoding="utf-8")
        assert paths.under(root, "nested/app.yaml") == target.resolve()

    def test_under_rejects_symlink_escape(self, tmp_path: Path) -> None:
        paths = ContractRelPath()
        root = tmp_path / "repo"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "app.yaml").write_text("x", encoding="utf-8")
        (root / "escape").symlink_to(outside)
        with pytest.raises(OperatorError, match="escapes checkout"):
            paths.under(root, "escape/app.yaml")
