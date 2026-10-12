"""Coverage for ACL edge paths (validation, eligibility, writers)."""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raft.core.core.config.settings.strategies.acl import AclSettingsParser
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.render.acl.effective import AclEffective
from raft.core.lifecycle.render.acl.http_gate_host import HttpGateHost
from raft.core.lifecycle.render.acl.inc_writer import AclIncWriter
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.acl.api import ServeAclApi
from raft.services.serve.acl.apply import ServeAclService
from raft.services.serve.acl.eligibility import AclEligibility
from raft.services.serve.acl.settings_write import GateAclSettingsWriter
from raft.services.serve.http.app import ServeAppFactory
from tests.unit.base import AppliedInventory, RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestAclCoverage(RaftTestCase):
    def test_settings_parser_rejects_non_mapping(self) -> None:
        with pytest.raises(OperatorError, match="acl must be a mapping"):
            AclSettingsParser().parse([])

    def test_policy_rejects_bad_shapes(self) -> None:
        with pytest.raises(OperatorError, match="must be a mapping"):
            AclPolicy.from_mapping([], path="acl.gate")
        with pytest.raises(OperatorError, match="mode must be"):
            AclPolicy.from_mapping({"mode": "maybe"}, path="acl.gate")
        with pytest.raises(OperatorError, match="entries must be a list"):
            AclPolicy.from_mapping({"mode": "off", "entries": {}}, path="acl.gate")
        with pytest.raises(OperatorError, match="must be a mapping"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": ["x"]}, path="acl.gate"
            )
        with pytest.raises(OperatorError, match="id is required"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": [{"cidr": "192.0.2.1"}]},
                path="acl.gate",
            )
        with pytest.raises(OperatorError, match="is required"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": [{"id": "x", "cidr": ""}]},
                path="acl.gate",
            )

    def test_store_list_and_corrupt_json(self) -> None:
        store = AppAclStore(self.tmp_path)
        store.save("demo-api", AclPolicy())
        assert store.list_names() == []
        path = store.path_for("broken")
        store.ensure_dirs()
        path.write_text("{not-json", encoding="utf-8")
        assert store.load("broken").mode == "off"
        store.delete("missing")

    def test_nginx_inactive_and_prune(self) -> None:
        assert AclNginxText.location_rules(AclPolicy()) == ""
        (self.tmp_path / "settings.yaml").write_text("edge: {}\n", encoding="utf-8")
        writer = AclIncWriter(
            self.tmp_path / "generated/nginx/gate-http", AclEffective(self.tmp_path)
        )
        writer.write_all([])
        stale = self.tmp_path / "generated/nginx/gate-http/acl/stale.inc"
        stale.write_text("x", encoding="utf-8")
        writer.write_all([])
        assert not stale.exists()

    def test_http_gate_host_skips(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            public_host="",
            extra={"ports": [], "readiness": {"type": "none"}},
        )
        host = HttpGateHost()
        app = StackMakers.make_app("demo-api")
        _, app_spec = AppDocument.load(
            AppRegistry(self.tmp_path).path_for("demo-api"), expect_name="demo-api"
        )
        assert (
            host.contribute(
                app, app_spec, edge=EdgeConfig(http=80), acl_include=""
            ).gate_http
            == []
        )
        wapp = StackMakers.make_app("worker", public_host="")
        _, wspec = AppDocument.load(
            AppRegistry(self.tmp_path).path_for("worker"), expect_name="worker"
        )
        assert (
            host.contribute(
                wapp, wspec, edge=EdgeConfig(http=80), acl_include="include x;\n"
            ).gate_http
            == []
        )

    def test_eligibility_missing_and_no_public_host(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = load_stack(self.tmp_path)
        elig = AclEligibility(stack)
        assert elig.meta("missing")["supported"] is False
        with pytest.raises(OperatorError, match="not applied"):
            elig.require_app("missing")
        from raft.core.core.models.app import App

        _, spec = AppDocument.load(
            AppRegistry(self.tmp_path).path_for("demo-api"), expect_name="demo-api"
        )
        bare = App(
            name="demo-api",
            public_host="",
            source="local",
            path="apps/demo-api",
            repo=None,
            ref="main",
            image=None,
        )
        with pytest.raises(OperatorError, match="publicHost"):
            AclEligibility._require_http_host(bare, spec)
        assert "expose: http" in AclEligibility._fix_line("no Fix line")

    def test_settings_write_clear_and_errors(self) -> None:
        writer = GateAclSettingsWriter(self.tmp_path)
        path = self.tmp_path / "settings.yaml"
        path.unlink()
        assert writer.put({"mode": "off", "entries": []})["mode"] == "off"
        assert writer.get_public()["mode"] == "off"
        assert writer.clear()["mode"] == "off"
        path.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            writer.put({"mode": "off", "entries": []})
        path.write_text("edge: {\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="cannot read"):
            writer.put({"mode": "off", "entries": []})

    def test_store_write_cleanup_on_replace_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = AppAclStore(self.tmp_path)
        store.ensure_dirs()

        def boom(*_args, **_kwargs):
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError, match="replace failed"):
            store.save(
                "demo-api",
                AclPolicy.from_mapping(
                    {
                        "mode": "whitelist",
                        "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
                    },
                    path="t",
                ),
            )
        assert list((self.tmp_path / "state/acl/apps").glob("*.tmp")) == []

    def test_api_operator_errors(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80}\n", encoding="utf-8"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = load_stack(self.tmp_path)
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        orch = MagicMock()
        service = ServeAclService(stack, orchestrator=orch)
        service.gate_clear = MagicMock(  # type: ignore[method-assign]
            side_effect=OperatorError("boom\nFix: retry", has_fix=False)
        )
        api = ServeAclApi(stack, service=service)
        client = TestClient(ServeAppFactory(stack, status=status, acl=api).create())
        bad = client.put("/api/acl/gate", json={"mode": "whitelist", "entries": []})
        assert bad.status_code == 400
        assert client.delete("/api/acl/gate").status_code == 400
        bad_app = client.get("/api/acl/apps/missing")
        assert bad_app.status_code == 400
        del_missing = client.delete("/api/acl/apps/missing")
        assert del_missing.status_code == 400
