"""ControlPlaneEvents kind/severity/context contract."""

from __future__ import annotations

from raft.services.notify.control_events import (
    KIND_ACME_ERROR,
    KIND_HEAL_ESCALATE,
    KIND_SCALE_WAKE_TIMEOUT,
    KIND_SERVE_DEPLOY_FAILED,
    ControlPlaneEvents,
)
from raft.services.notify.event import NotificationSeverity

from ...base import RaftTestCase


class TestControlPlaneEvents(RaftTestCase):
    def test_heal_and_wake(self) -> None:
        heal = ControlPlaneEvents.heal_escalate(
            "demo-api", compose_id="demo-api", restarts=2
        )
        assert heal.kind == KIND_HEAL_ESCALATE
        assert heal.severity == NotificationSeverity.ERROR
        assert heal.context["app"] == "demo-api"
        wake = ControlPlaneEvents.scale_wake_timeout(
            "demo-api", wake_id="abc123", timeout_seconds=60, detail="wait_running"
        )
        assert wake.kind == KIND_SCALE_WAKE_TIMEOUT
        assert wake.severity == NotificationSeverity.WARNING
        assert wake.context["id"] == "abc123"

    def test_acme_and_deploy(self) -> None:
        acme = ControlPlaneEvents.acme_last_error("demo-api", error="DNS not ready")
        assert acme.kind == KIND_ACME_ERROR
        assert "DNS not ready" in acme.context["last_error"]
        dep = ControlPlaneEvents.serve_deploy_failed(
            job_id="j1", full_name="demo-org/demo-api", error="boom"
        )
        assert dep.kind == KIND_SERVE_DEPLOY_FAILED
        assert dep.context["full_name"] == "demo-org/demo-api"
