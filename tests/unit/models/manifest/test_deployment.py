"""Unit tests for ``spec.deployment`` parse/validation."""

from __future__ import annotations

import pytest

from raft.errors.cta import OperatorError
from raft.models.app_document import AppDocument
from raft.models.deployment_spec import DeploymentSpec

from .base import ManifestTestCase


class TestDeploymentSpec(ManifestTestCase):
    def test_omit_defaults_to_seamless(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        spec = AppDocument.load_contract(checkout)
        assert spec.deployment == DeploymentSpec(method="seamless")

    def test_empty_object_defaults_method(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n  deployment: {}\n",
            encoding="utf-8",
        )
        spec = AppDocument.load_contract(checkout)
        assert spec.deployment.method == "seamless"

    def test_seamless_explicit(self) -> None:
        spec = self._load_with_deployment("method: seamless")
        assert spec.deployment.method == "seamless"

    def test_inplace(self) -> None:
        spec = self._load_with_deployment("method: inplace")
        assert spec.deployment.method == "inplace"

    def test_invalid_method_is_operator_error(self) -> None:
        with pytest.raises(OperatorError, match="spec.deployment.method") as caught:
            self._load_with_deployment("method: blue-green")
        assert "Fix:" in str(caught.value)

    def test_rejects_non_object(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n  deployment: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must be an object"):
            AppDocument.load_contract(checkout)

    def test_rejects_unknown_keys(self) -> None:
        with pytest.raises(ValueError, match="unknown keys"):
            self._load_with_deployment("method: seamless\n    strategy: x")

    def test_empty_method_errors(self) -> None:
        with pytest.raises(OperatorError, match="spec.deployment.method"):
            self._load_with_deployment("method: ''")

    def _load_with_deployment(self, body: str):
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + f"\n  deployment:\n    {body}\n", encoding="utf-8")
        return AppDocument.load_contract(checkout)
