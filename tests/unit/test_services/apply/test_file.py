"""Apply from local file coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.models.stack import load_stack
from raft.services.apply import AppApply

from ...base import write_applied_app
from .base import ApplyTestCase


class TestApplyFile(ApplyTestCase):
    def test_apply_file_no_deploy(self, capsys) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(self.manifest()), encoding="utf-8")
        stack = load_stack(self.tmp_path)
        name = AppApply(stack).apply_file(path, deploy=False)
        assert name == "web"
        assert (self.tmp_path / "state" / "apps" / "web.yaml").is_file()
        assert "applied web" in capsys.readouterr().out

    def test_apply_file_rejects_non_mapping(self) -> None:
        path = self.tmp_path / "bad.yaml"
        path.write_text("- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)

    def test_apply_file_missing_and_bad_yaml(self) -> None:
        missing = self.tmp_path / "nope.yaml"
        with pytest.raises(RuntimeError, match="cannot read App manifest"):
            AppApply(load_stack(self.tmp_path)).apply_file(missing, deploy=False)
        path = self.tmp_path / "bad.yaml"
        path.write_text("{{{{", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid App manifest YAML"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)

    def test_apply_file_ref_override_and_bad_spec(self) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(
            yaml.safe_dump(self.manifest()),
            encoding="utf-8",
        )
        AppApply(load_stack(self.tmp_path)).apply_file(path, ref_override="v2", deploy=False)
        data = yaml.safe_load(
            (self.tmp_path / "state" / "apps" / "web.yaml").read_text(encoding="utf-8")
        )
        assert data["spec"]["ref"] == "v2"

        path.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: x\nspec: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec must be an object"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, ref_override="x", deploy=False)

    def test_apply_file_deploys_running_and_new(self) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(self.manifest()), encoding="utf-8")
        stack = load_stack(self.tmp_path)
        applier = AppApply(stack)

        orch = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch):
            with patch("raft.services.apply.load_stack", return_value=stack):
                applier.apply_file(path, deploy=True)
        orch.ensure_app_deployed.assert_called_once_with(
            "web", ref_override=None, force_sync=False
        )

        orch2 = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch2):
            with patch("raft.services.apply.load_stack", return_value=stack):
                applier.apply_file(path, deploy=True, force_sync=True)
        orch2.ensure_app_deployed.assert_called_once_with(
            "web", ref_override=None, force_sync=True
        )

