"""Unit tests for ``AppDefinitionRead``."""

from raft.core.core.models.stack import Stack
from raft.core.observe.read.definition import AppDefinitionRead
from tests.unit.base import AppliedInventory, RaftTestCase


class TestAppDefinitionRead(RaftTestCase):
    def test_returns_raw_yaml_for_app(self) -> None:
        path = AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = Stack.load_apps(self.tmp_path)
        payload = AppDefinitionRead(stack).for_service("demo-api")
        assert payload["eligible"] is True
        assert payload["app"] == "demo-api"
        assert payload["path"] == "services/demo-api/app.yaml"
        assert payload["yaml"] == path.read_text(encoding="utf-8")
        assert "demo-api" in payload["yaml"]

    def test_resolves_compose_id(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "demo-api",
            public_host="demo-api.test",
            extra={"group": "web"},
        )
        stack = Stack.load_apps(self.tmp_path)
        payload = AppDefinitionRead(stack).for_service("web-demo-api")
        assert payload["eligible"] is True
        assert payload["service"] == "web-demo-api"
        assert payload["app"] == "demo-api"

    def test_edge_ineligible(self) -> None:
        stack = Stack.load_apps(self.tmp_path)
        payload = AppDefinitionRead(stack).for_service("raft-gate")
        assert payload["eligible"] is False
        assert payload["yaml"] is None
        assert "no applied App manifest" in (payload["reason"] or "")

    def test_unknown_marked(self) -> None:
        stack = Stack.load_apps(self.tmp_path)
        payload = AppDefinitionRead(stack).for_service("no-such")
        assert payload["unknown"] is True
        assert payload["eligible"] is False

    def test_missing_file_ineligible(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = Stack.load_apps(self.tmp_path)
        path = self.tmp_path / "services" / "demo-api" / "app.yaml"
        path.unlink()
        payload = AppDefinitionRead(stack).for_service("demo-api")
        assert payload["eligible"] is False
        assert payload["yaml"] is None
        assert "missing" in (payload["reason"] or "")

    def test_bind_stack(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        empty = Stack.load_apps(self.tmp_path / "empty")
        reader = AppDefinitionRead(empty)
        reader.bind_stack(Stack.load_apps(self.tmp_path))
        assert reader.for_service("demo-api")["eligible"] is True

    def test_skips_non_matching_apps(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-web", public_host="demo-web.test"
        )
        stack = Stack.load_apps(self.tmp_path)
        payload = AppDefinitionRead(stack).for_service("demo-web")
        assert payload["eligible"] is True
        assert payload["app"] == "demo-web"
