"""Firewall recommendations and dismissal persistence."""

from unittest.mock import MagicMock, patch

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.recommendation_dismissals import (
    FirewallDismissalStore,
)
from raft.core.core.models.state.firewall_store import FirewallStore
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.firewall.eligibility import FirewallEligibility
from raft.core.lifecycle.firewall.recommendations import FirewallRecommendations
from tests.unit.base import AppliedInventory, RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import document, rule_dict


class TestFirewallRecommendations(RaftTestCase):
    def _prep(self, edge: str = "edge: {http: 80, https: 443}\n") -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(edge, encoding="utf-8")

    def test_baseline_and_dismiss(self) -> None:
        self._prep()
        recs = FirewallRecommendations(self.tmp_path)
        items = recs.list_public()["recommendations"]
        ids = {item["id"] for item in items}
        assert ids == {"permit-port-80", "permit-port-443", "default-deny"}
        assert items[-1]["append"] is True
        recs.dismiss("permit-port-80")
        left = {item["id"] for item in recs.list_public()["recommendations"]}
        assert "permit-port-80" not in left
        assert FirewallDismissalStore(self.tmp_path).list_ids() == {"permit-port-80"}

    def test_hides_when_rules_cover_baseline(self) -> None:
        self._prep("edge: {http: 80, https: null}\n")
        FirewallStore(self.tmp_path).save(
            document(
                rule_dict("p80", port=80, action="permit", cidr="0.0.0.0/0"),
                rule_dict(
                    "deny-all",
                    port="any",
                    action="deny",
                    cidr="0.0.0.0/0",
                    protocol="any",
                ),
            )
        )
        items = FirewallRecommendations(self.tmp_path).list_public()["recommendations"]
        assert items == []

    def test_eligibility_meta(self) -> None:
        self._prep("edge: {http: 80}\n")
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            public_host="",
            extra={"ports": [], "readiness": {"type": "none"}},
        )
        elig = FirewallEligibility(load_stack(self.tmp_path))
        assert elig.meta("demo-api")["supported"] is True
        assert elig.meta("worker")["supported"] is False
        assert elig.meta("missing")["supported"] is False
        assert "expose: http" in FirewallEligibility._fix_line("no Fix line")
        self._require_public_host()

    def _require_public_host(self) -> None:
        app = MagicMock(name="bare", public_host="")
        app.name = "bare"
        port = MagicMock(expose="http")
        try:
            FirewallEligibility._require_http_host(app, MagicMock(ports=[port]))
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "requires publicHost" in str(exc)

    def test_edge_ports_fallback(self) -> None:
        self._prep("edge: {http: null, https: null}\n")
        ids = {
            item["id"]
            for item in FirewallRecommendations(self.tmp_path).list_public()[
                "recommendations"
            ]
        }
        assert "permit-port-80" in ids

    def test_dismissal_corrupt_and_blank(self) -> None:
        store = FirewallDismissalStore(self.tmp_path)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("[1,2,3]\n", encoding="utf-8")
        assert store.list_ids() == frozenset()
        store.path.write_text('{"dismissed": "x"}\n', encoding="utf-8")
        assert store.list_ids() == frozenset()
        store.path.write_text("{bad", encoding="utf-8")
        assert store.list_ids() == frozenset()
        assert store.dismiss("  ") == frozenset()
        with patch("os.replace", side_effect=OSError("boom")):
            try:
                store.dismiss("x")
            except OSError:
                pass
        assert list(store.root.glob("*.tmp")) == []

