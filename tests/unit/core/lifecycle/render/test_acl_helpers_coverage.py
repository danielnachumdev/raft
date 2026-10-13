"""Coverage for leftover ACL helpers (migrate/clear/nginx text only)."""

import os

import pytest

from raft.core.core.config.settings.strategies.acl import AclSettingsParser
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.state.acl_store import AppAclStore
from raft.core.lifecycle.render.acl.effective import AclEffective
from raft.core.lifecycle.render.acl.http_gate_host import HttpGateHost
from raft.core.lifecycle.render.acl.inc_writer import AclIncWriter
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from tests.unit.base import AppliedInventory, RaftTestCase, StackMakers


class TestAclHelpersCoverage(RaftTestCase):
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
        self._assert_entry_shape_errors()

    def test_store_list_and_corrupt_json(self) -> None:
        store = AppAclStore(self.tmp_path)
        assert store.load("missing").mode == "off"
        store.save("demo-api", self._lab_policy())
        assert "demo-api" in store.list_names()
        store.delete("demo-api")
        path = store.path_for("broken")
        store.ensure_dirs()
        path.write_text("{not-json", encoding="utf-8")
        assert store.load("broken").mode == "off"
        store.delete("missing")

    def test_inactive_includes(self) -> None:
        assert AclNginxText.location_rules(AclPolicy()) == ""
        (self.tmp_path / "settings.yaml").write_text("edge: {}\n", encoding="utf-8")
        empty = AclIncWriter(
            self.tmp_path / "generated/nginx/gate-http", AclEffective(self.tmp_path)
        )
        assert empty.gate_include() == ""
        assert empty.host_include("missing") == ""
        assert AclEffective(self.tmp_path).host_policy("missing").mode == "off"

    def test_nginx_write_prune_and_host(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {}\n"
            "acl:\n  gate:\n    mode: blacklist\n"
            "    entries:\n      - {id: bad, cidr: 198.51.100.10}\n",
            encoding="utf-8",
        )
        writer = AclIncWriter(
            self.tmp_path / "generated/nginx/gate-http", AclEffective(self.tmp_path)
        )
        writer.write_all([])
        assert writer.gate_include()
        stale = self.tmp_path / "generated/nginx/gate-http/acl/stale.inc"
        stale.write_text("x", encoding="utf-8")
        writer.write_all([])
        assert not stale.exists()
        self._assert_host_policy_include()

    def _assert_host_policy_include(self) -> None:
        AppAclStore(self.tmp_path).save("demo-api", self._lab_policy())
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        writer = AclIncWriter(
            self.tmp_path / "generated/nginx/gate-http", AclEffective(self.tmp_path)
        )
        app = StackMakers.make_app("demo-api", public_host="demo-api.test")
        writer.write_all([app])
        assert writer.host_include("demo-api")
        assert AclEffective(self.tmp_path).needs_host_gate_server("demo-api")

    def test_http_gate_host_skips(self) -> None:
        self._write_demo_and_worker()
        host = HttpGateHost()
        app, app_spec = self._load_app("demo-api")
        assert (
            host.contribute(
                app, app_spec, edge=EdgeConfig(http=80), acl_include=""
            ).gate_http
            == []
        )
        wapp, wspec = self._load_app("worker")
        assert (
            host.contribute(
                wapp, wspec, edge=EdgeConfig(http=80), acl_include="include x;\n"
            ).gate_http
            == []
        )

    def test_store_write_cleanup_on_replace_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = AppAclStore(self.tmp_path)
        store.ensure_dirs()
        monkeypatch.setattr(os, "replace", self._boom_replace)
        with pytest.raises(OSError, match="replace failed"):
            store.save("demo-api", self._lab_policy())
        assert list((self.tmp_path / "state/acl/apps").glob("*.tmp")) == []

    @staticmethod
    def _boom_replace(*_args, **_kwargs):
        raise OSError("replace failed")

    @staticmethod
    def _lab_policy() -> AclPolicy:
        return AclPolicy.from_mapping(
            {
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            },
            path="t",
        )

    def _assert_entry_shape_errors(self) -> None:
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

    def _write_demo_and_worker(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            public_host="",
            extra={"ports": [], "readiness": {"type": "none"}},
        )

    def _load_app(self, name: str):
        app = StackMakers.make_app(
            name, public_host="" if name == "worker" else "demo-api.test"
        )
        _, spec = AppDocument.load(
            AppRegistry(self.tmp_path).path_for(name), expect_name=name
        )
        return app, spec
