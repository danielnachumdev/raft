"""Unit tests for ``spec.unavailablePage`` / ``spec.forbiddenPage``."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app_document import AppDocument

from tests.unit.core.core.models.manifest.base import ManifestTestCase


class TestEdgePageFields(ManifestTestCase):
    def test_parse_both_pages(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        text += (
            "\n  unavailablePage: .raft/unavailable.html\n"
            "  forbiddenPage: .raft/forbidden.html\n"
        )
        path.write_text(text, encoding="utf-8")
        spec = AppDocument.load_contract(checkout)
        assert spec.unavailable_page == ".raft/unavailable.html"
        assert spec.forbidden_page == ".raft/forbidden.html"

    def test_snake_aliases(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        text = path.read_text(encoding="utf-8")
        text += (
            "\n  unavailable_page: .raft/u.html\n"
            "  forbidden_page: .raft/f.html\n"
        )
        path.write_text(text, encoding="utf-8")
        spec = AppDocument.load_contract(checkout)
        assert spec.unavailable_page == ".raft/u.html"
        assert spec.forbidden_page == ".raft/f.html"

    def test_rejects_without_public_host(self) -> None:
        path = self.tmp_path / "worker.yaml"
        path.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: worker\n"
            "spec:\n  source: local\n  path: services/worker/checkout\n"
            "  ports: []\n"
            "  unavailablePage: .raft/unavailable.html\n"
            "  build:\n    context: .\n",
            encoding="utf-8",
        )
        with pytest.raises(OperatorError, match="publicHost"):
            AppDocument.load(path)

    def test_rejects_absolute_and_parent(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        base = path.read_text(encoding="utf-8")
        path.write_text(base + "\n  unavailablePage: /etc/passwd\n", encoding="utf-8")
        with pytest.raises(ValueError, match="relative"):
            AppDocument.load_contract(checkout)
        path.write_text(
            base + "\n  forbiddenPage: ../escape.html\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="\\.\\."):
            AppDocument.load_contract(checkout)

    def test_rejects_blank(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        base = path.read_text(encoding="utf-8")
        path.write_text(base + "\n  unavailablePage: '  '\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-empty"):
            AppDocument.load_contract(checkout)

    def test_rejects_home_relative(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout)
        path = checkout / ".raft" / "app.yaml"
        base = path.read_text(encoding="utf-8")
        path.write_text(
            base + "\n  forbiddenPage: ~/forbidden.html\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="relative"):
            AppDocument.load_contract(checkout)
