"""Final coverage gaps A: model + kinds + stores."""

from pathlib import Path

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.kinds.event_count import EventCountKind
from raft.core.observe.alerts.kinds.state_match import StateMatchKind
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from raft.core.observe.alerts.model.condition import ConditionGroup, ConditionLeaf
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.store.rules_store import AlertRulesStore
from raft.core.observe.alerts.catalogs import AlertCatalogs
from tests.unit.base import RaftTestCase


class TestFinalGapsA(RaftTestCase):
    def test_condition_public_and_document_list(self) -> None:
        leaf = ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {})
        assert leaf.to_public()["signal"] == "metrics.http"
        group = ConditionGroup("all", (leaf,))
        assert "all" in group.to_public()
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping({"rules": "bad"}, registries=AlertCatalogs.default())

    def test_kind_validate_edges(self) -> None:
        assert any(
            "op" in i.path
            for i in ThresholdKind().validate_params(
                {"aggregate": "avg", "op": "xx", "value": 1}, path="p"
            )
        )
        assert any(
            "window" in i.path
            for i in EventCountKind().validate_params(
                {"op": "gte", "value": 1, "window": "bad"}, path="p"
            )
        )
        assert StateMatchKind().validate_params(
            {"match": "in", "values": ["running"]}, path="p"
        ) == []

    def test_rules_store_exists_and_corrupt(self) -> None:
        home = Path(self.tmp_path)
        store = AlertRulesStore(home)
        assert store.exists() is False
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        store.path.write_bytes(b"\xff\xfe")
        with pytest.raises(OperatorError):
            store.load_raw()
