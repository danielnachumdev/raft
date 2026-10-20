"""Coverage for shared ACL nginx text helpers still used by firewall render."""

import pytest

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.registry import AppRegistry
from raft.core.lifecycle.render.acl.http_gate_host import HttpGateHost
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from tests.unit.base import AppliedInventory, RaftTestCase, StackMakers


class TestAclHelpersCoverage(RaftTestCase):
    def test_policy_rejects_bad_shapes(self) -> None:
        with pytest.raises(OperatorError, match="must be a mapping"):
            AclPolicy.from_mapping([], path="policy")
        with pytest.raises(OperatorError, match="mode must be"):
            AclPolicy.from_mapping({"mode": "maybe"}, path="policy")
        with pytest.raises(OperatorError, match="entries must be a list"):
            AclPolicy.from_mapping({"mode": "off", "entries": {}}, path="policy")
        self._assert_entry_shape_errors()

    def test_inactive_location_rules(self) -> None:
        assert AclNginxText.location_rules(AclPolicy()) == ""

    def test_whitelist_and_blacklist_location_rules(self) -> None:
        white = AclPolicy.from_mapping(
            {
                "mode": "whitelist",
                "entries": [{"id": "lab", "cidr": "192.0.2.0/24"}],
            },
            path="policy",
        )
        text = AclNginxText.location_rules(white)
        assert "allow 192.0.2.0/24;" in text and "deny all;" in text
        black = AclPolicy.from_mapping(
            {
                "mode": "blacklist",
                "entries": [{"id": "bad", "cidr": "198.51.100.10"}],
            },
            path="policy",
        )
        text = AclNginxText.location_rules(black)
        assert "deny 198.51.100.10/32;" in text and "allow all;" in text
        assert AclNginxText.include_line("_gate.inc").endswith("acl/_gate.inc;\n")
        assert "_raft_forbidden" in AclNginxText.forbidden_location()

    def test_entries_none_parses_empty(self) -> None:
        policy = AclPolicy.from_mapping({"mode": "off", "entries": None}, path="policy")
        assert policy.entries == ()

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

    def _assert_entry_shape_errors(self) -> None:
        with pytest.raises(OperatorError, match="must be a mapping"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": ["x"]}, path="policy"
            )
        with pytest.raises(OperatorError, match="id is required"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": [{"cidr": "192.0.2.1"}]},
                path="policy",
            )
        with pytest.raises(OperatorError, match="is required"):
            AclPolicy.from_mapping(
                {"mode": "blacklist", "entries": [{"id": "x", "cidr": ""}]},
                path="policy",
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
