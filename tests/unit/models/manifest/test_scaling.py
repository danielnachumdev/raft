"""Unit tests for ``spec.scaling`` parse/validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument
from raft.models.scaling_spec import ScalingSpec

from .base import ManifestTestCase


class TestScalingSpec(ManifestTestCase):
    def test_omit_means_no_scaling(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        spec = AppDocument.load_contract(checkout)
        assert spec.scaling is None

    def test_all_fields_required(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        text += "\n  scaling:\n    idleSeconds: 60\n"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="wakeTimeoutSeconds"):
            AppDocument.load_contract(checkout)

    def test_positive_numbers(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        text += (
            "\n  scaling:\n"
            "    idleSeconds: 30\n"
            "    wakeTimeoutSeconds: 60\n"
            "    minUpSeconds: 15\n"
        )
        path.write_text(text, encoding="utf-8")
        spec = AppDocument.load_contract(checkout)
        assert spec.scaling == ScalingSpec(
            idle_seconds=30.0, wake_timeout_seconds=60.0, min_up_seconds=15.0
        )

    def test_rejects_non_http_only(self) -> None:
        path = self.tmp_path / "stream.yaml"
        path.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: mail\n"
            "spec:\n  source: local\n  path: apps/mail\n  ports:\n"
            "    - name: smtp\n      containerPort: 25\n"
            "      expose: stream\n      publicPort: 25\n"
            "  scaling:\n    idleSeconds: 10\n"
            "    wakeTimeoutSeconds: 20\n    minUpSeconds: 5\n"
            "  build:\n    context: .\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="expose: http"):
            AppDocument.load(path)

    def test_rejects_non_object_and_bad_number(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\n  scaling: []\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be an object"):
            AppDocument.load_contract(checkout)
        path.write_text(
            text
            + "\n  scaling:\n    idleSeconds: nope\n"
            + "    wakeTimeoutSeconds: 1\n    minUpSeconds: 1\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="positive number"):
            AppDocument.load_contract(checkout)

    def test_snake_case_keys(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text
            + "\n  scaling:\n    idle_seconds: 11\n"
            + "    wake_timeout_seconds: 22\n    min_up_seconds: 33\n",
            encoding="utf-8",
        )
        spec = AppDocument.load_contract(checkout)
        assert spec.scaling == ScalingSpec(11.0, 22.0, 33.0)

    def test_rejects_zero_idle(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text
            + "\n  scaling:\n    idleSeconds: 0\n"
            + "    wakeTimeoutSeconds: 60\n    minUpSeconds: 15\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="idleSeconds"):
            AppDocument.load_contract(checkout)
