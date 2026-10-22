"""Dual-read aliases for persisted graph/ops event kinds."""

from raft.core.core.models.state.graph_event_kinds import (
    KIND_GATE_REDEPLOY as GRAPH_GATE_REDEPLOY,
    LEGACY_KIND_GATE_RECREATE as GRAPH_LEGACY_GATE_RECREATE,
    GraphKindAliases,
)
from raft.core.core.models.state.ops_event_kinds import (
    KIND_GATE_REDEPLOY as OPS_GATE_REDEPLOY,
    KIND_SERVICE_DOWN,
    KIND_SERVICE_UP,
    LEGACY_KIND_GATE_RECREATE as OPS_LEGACY_GATE_RECREATE,
    LEGACY_KIND_SERVICE_START,
    LEGACY_KIND_SERVICE_STOP,
    OpsKindAliases,
)
from tests.unit.base import RaftTestCase


class TestGraphKindAliases(RaftTestCase):
    def test_canonical_gate_redeploy(self) -> None:
        assert (
            GraphKindAliases.canonical(GRAPH_LEGACY_GATE_RECREATE)
            == GRAPH_GATE_REDEPLOY
        )
        assert GraphKindAliases.canonical(GRAPH_GATE_REDEPLOY) == GRAPH_GATE_REDEPLOY

    def test_matches_legacy_and_new(self) -> None:
        assert GraphKindAliases.matches(
            GRAPH_LEGACY_GATE_RECREATE, GRAPH_GATE_REDEPLOY
        )
        assert GraphKindAliases.matches(
            GRAPH_GATE_REDEPLOY, GRAPH_LEGACY_GATE_RECREATE
        )


class TestOpsKindAliases(RaftTestCase):
    def test_canonical_gate_and_service(self) -> None:
        assert OpsKindAliases.canonical(OPS_LEGACY_GATE_RECREATE) == OPS_GATE_REDEPLOY
        assert OpsKindAliases.canonical(LEGACY_KIND_SERVICE_START) == KIND_SERVICE_UP
        assert OpsKindAliases.canonical(LEGACY_KIND_SERVICE_STOP) == KIND_SERVICE_DOWN

    def test_matches_legacy_and_new(self) -> None:
        assert OpsKindAliases.matches(OPS_LEGACY_GATE_RECREATE, OPS_GATE_REDEPLOY)
        assert OpsKindAliases.matches(LEGACY_KIND_SERVICE_START, KIND_SERVICE_UP)
