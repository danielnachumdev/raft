"""Apply refuses cross-source takeover of metadata.name."""

from unittest.mock import patch

import yaml

from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.apply import AppApply

from tests.unit.base import AppliedInventory
from tests.unit.core.lifecycle.apply.base import ApplyTestCase
from tests.unit.cta_asserts import CtaAsserts


class TestApplySourceOwnership(ApplyTestCase):
    def test_same_source_reapply_ok(self) -> None:
        path = self._write_manifest(
            self.manifest(
                "demo-api",
                source="git",
                repo="git@github.com:demo-org/demo-api.git",
                public_host="demo-api.test",
            )
        )
        AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)
        AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)
        assert (self.tmp_path / "state" / "apps" / "demo-api.yaml").is_file()

    def test_different_source_denied(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            source="git",
            repo="git@github.com:demo-org/demo-api.git",
            public_host="demo-api.test",
        )
        path = self._write_manifest(
            self.manifest(
                "demo-api",
                source="git",
                repo="git@github.com:other-org/other-api.git",
                public_host="other.test",
            )
        )
        with CtaAsserts.raises(
            match="different source",
            contains=("demo-org/demo-api", "other-org/other-api", "raft delete"),
        ):
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)

    def test_delete_then_reapply_from_new_source(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            source="local",
            path="apps/demo-api",
            public_host="demo-api.test",
        )
        with patch("raft.core.lifecycle.apply.service.Orchestrator"):
            AppApply(load_stack(self.tmp_path)).delete("demo-api")
        path = self._write_manifest(self._docker_manifest("demo-api"))
        name = AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)
        assert name == "demo-api"

    def _write_manifest(self, doc: dict):
        path = self.tmp_path / "incoming.yaml"
        path.write_text(yaml.safe_dump(doc), encoding="utf-8")
        return path

    @staticmethod
    def _docker_manifest(name: str) -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": {
                "publicHost": f"{name}.test",
                "source": "docker",
                "image": "ghcr.io/demo-org/demo-api",
                "ref": "main",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }