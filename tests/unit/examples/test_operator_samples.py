"""Smoke-parse operator examples (firewall + worker + alerts shape)."""

from __future__ import annotations

from pathlib import Path

import yaml

from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.firewall import FirewallDocument
from tests.unit.base import RaftTestCase

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples"


class TestOperatorSamples(RaftTestCase):
    def test_firewall_rules_sample(self) -> None:
        path = EXAMPLES / "firewall" / "rules.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc = FirewallDocument.from_mapping(raw, path=str(path))
        assert doc.version == 1
        assert len(doc.rules) >= 1
        assert all(r.cidr.startswith(("192.0.2.", "0.0.0.0")) for r in doc.rules)

    def test_alerts_rules_sample_shape(self) -> None:
        path = EXAMPLES / "alerts" / "rules.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert raw["version"] == 1
        ids = {r["id"] for r in raw["rules"]}
        assert ids >= {"demo-api-5xx-rate", "demo-api-container-down"}
        for rule in raw["rules"]:
            assert "for" in rule and "cooldown" in rule
            assert "signal" in rule["condition"]

    def test_alerts_rules_sample_parses(self) -> None:
        from raft.core.observe.alerts.catalogs import AlertCatalogs
        from raft.core.observe.alerts.model.document import AlertRulesDocument

        path = EXAMPLES / "alerts" / "rules.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc = AlertRulesDocument.from_mapping(
            raw, registries=AlertCatalogs.default(), path=str(path)
        )
        assert len(doc.rules) == 2

    def test_worker_app_sample(self) -> None:
        path = EXAMPLES / "worker-app" / ".raft" / "app.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        _app, spec = AppDocument.parse(raw, path=path)
        assert spec.ports == ()
        assert spec.readiness.type == "none"
        assert spec.tls == "off"
