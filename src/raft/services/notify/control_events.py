"""Typed control-plane notification events (producers build these only)."""

from __future__ import annotations

from .event import NotificationEvent, NotificationSeverity

KIND_HEAL_ESCALATE = "heal.escalate"
KIND_SCALE_WAKE_TIMEOUT = "scale.wake_timeout"
KIND_ACME_ERROR = "acme.last_error"
KIND_SERVE_DEPLOY_FAILED = "serve.deploy_failed"


class ControlPlaneEvents:
    """Factory for epic #158 producer events (no channel-type knowledge)."""

    @staticmethod
    def heal_escalate(
        app: str, *, compose_id: str, restarts: int
    ) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_HEAL_ESCALATE,
            severity=NotificationSeverity.ERROR,
            title=f"Heal escalate: {app}",
            body=(
                f"App {app} exhausted Compose restarts ({restarts}); "
                f"escalating to redeploy/cutover."
            ),
            context={
                "app": app,
                "compose_id": compose_id,
                "restarts": restarts,
            },
        )

    @staticmethod
    def scale_wake_timeout(
        app: str, *, wake_id: str, timeout_seconds: float, detail: str
    ) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_SCALE_WAKE_TIMEOUT,
            severity=NotificationSeverity.WARNING,
            title=f"Scale wake timeout: {app}",
            body=(
                f"App {app} did not become ready within "
                f"{timeout_seconds:.0f}s (id={wake_id or '-'})."
            ),
            context={
                "app": app,
                "id": wake_id or "",
                "timeout_seconds": timeout_seconds,
                "detail": detail,
            },
        )

    @staticmethod
    def acme_last_error(app: str, *, error: str) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_ACME_ERROR,
            severity=NotificationSeverity.ERROR,
            title=f"ACME error: {app}",
            body=f"ACME for {app} recorded lastError.",
            context={"app": app, "last_error": error},
        )

    @staticmethod
    def serve_deploy_failed(
        *, job_id: str, full_name: str, error: str
    ) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_SERVE_DEPLOY_FAILED,
            severity=NotificationSeverity.ERROR,
            title=f"Deploy failed: {full_name}",
            body=f"Serve deploy job {job_id} failed for {full_name}.",
            context={
                "job_id": job_id,
                "full_name": full_name,
                "error": error[:500],
            },
        )
