"""Decide whether an App can use Host-routed HTTP ACL in v1."""

from typing import Any, Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.stack import Stack


class AclEligibility:
    """v1: only ``expose: http`` + ``publicHost`` Apps (Host-routed)."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def require_app(self, name: str) -> tuple[App, AppSpec]:
        app = self._find_app(name)
        if app is None:
            raise OperatorError(
                f"app '{name}' is not applied.\n"
                f"Fix: raft apply --file … (or --git …) then retry ACL",
                has_fix=False,
            )
        _, spec = self._load_spec(app)
        self._require_http_host(app, spec)
        return app, spec

    def meta(self, name: str) -> dict[str, Any]:
        app = self._find_app(name)
        if app is None:
            return {
                "supported": False,
                "reason": f"app '{name}' is not applied",
                "fix": "raft apply --file … then open Access control again",
            }
        _, spec = self._load_spec(app)
        return self._meta_for_spec(app, spec)

    def _meta_for_spec(self, app: App, spec: AppSpec) -> dict[str, Any]:
        try:
            self._require_http_host(app, spec)
        except OperatorError as exc:
            return {
                "supported": False,
                "reason": str(exc).split("\n")[0],
                "fix": self._fix_line(str(exc)),
            }
        return {
            "supported": True,
            "publicHost": app.public_host,
            "exposes": sorted({p.expose for p in spec.ports}),
        }

    def _load_spec(self, app: App) -> tuple[App, AppSpec]:
        return AppDocument.load(
            AppRegistry(self._stack.root).path_for(app.name),
            expect_name=app.name,
        )

    def _find_app(self, name: str) -> Optional[App]:
        for app in self._stack.apps:
            if app.name == name or app.compose_id == name:
                return app
        return None

    @staticmethod
    def _require_http_host(app: App, spec: AppSpec) -> None:
        http_ports = [p for p in spec.ports if p.expose == "http"]
        if not http_ports:
            raise OperatorError(
                f"{app.name}: ACL v1 supports only Host-routed HTTP Apps "
                f"(expose: http + publicHost). "
                f"stream/host/none/worker Apps are out of scope.\n"
                f"Fix: add an expose: http port and publicHost, or manage "
                f"access outside raft serve ACL",
                has_fix=False,
            )
        if not app.public_host:
            raise OperatorError(
                f"{app.name}: ACL v1 requires publicHost for Host-routed HTTP.\n"
                f"Fix: set spec.publicHost on the App manifest and re-apply",
                has_fix=False,
            )

    @staticmethod
    def _fix_line(message: str) -> str:
        for line in message.splitlines():
            if line.startswith("Fix:"):
                return line[len("Fix:") :].strip()
        return "use an expose: http App with publicHost"
