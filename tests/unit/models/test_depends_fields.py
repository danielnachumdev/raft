"""DependsOnFields parse coverage for string/object ``scaleWithParent``."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument
from raft.models.depends import DependsOnSpec


class TestDependsOnFields:
    PATH = Path("app.yaml")

    def _parse(self, depends_on) -> tuple:
        data = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "web"},
            "spec": {
                "source": "docker",
                "image": "hashicorp/http-echo",
                "ref": "1.0.0",
                "path": "apps/web",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                "publicHost": "web.test",
                "dependsOn": depends_on,
            },
        }
        _, spec = AppDocument.parse(data, path=self.PATH)
        return spec.depends_on

    def test_string_defaults_scale_with_parent_true(self) -> None:
        deps = self._parse("api")
        assert deps == (DependsOnSpec(name="api", scale_with_parent=True),)

    def test_object_omitted_flag_defaults_true(self) -> None:
        deps = self._parse([{"name": "api"}])
        assert deps == (DependsOnSpec(name="api", scale_with_parent=True),)

    def test_object_false_and_mixed(self) -> None:
        deps = self._parse(
            [
                "api",
                {"name": "sidecar", "scaleWithParent": False},
            ]
        )
        assert deps == (
            DependsOnSpec(name="api", scale_with_parent=True),
            DependsOnSpec(name="sidecar", scale_with_parent=False),
        )

    def test_snake_case_flag_accepted(self) -> None:
        deps = self._parse([{"name": "api", "scale_with_parent": False}])
        assert deps[0].scale_with_parent is False

    def test_unknown_key_errors(self) -> None:
        with pytest.raises(ValueError, match="unknown keys"):
            self._parse([{"name": "api", "extra": True}])

    def test_object_requires_name(self) -> None:
        with pytest.raises(ValueError, match="requires name"):
            self._parse([{"scaleWithParent": True}])

    def test_object_empty_name_errors(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            self._parse([{"name": "   "}])

    def test_flag_must_be_bool(self) -> None:
        with pytest.raises(ValueError, match="scaleWithParent must be a boolean"):
            self._parse([{"name": "api", "scaleWithParent": "yes"}])

    def test_entry_type_error(self) -> None:
        with pytest.raises(ValueError, match="strings or objects"):
            self._parse([1])
