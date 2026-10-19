"""Enable / disable / status for the always-on dashboard Compose service."""

from typing import Any, Dict, Optional

from raft.core.core.config.settings.dashboard_config import DASHBOARD_SERVICE_NAME
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.acme.ensure import AcmeEnsure
from raft.core.lifecycle.acme.install import AcmeGateInstall
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.adapters.shell import Shell
from raft.core.platform.locking import StackLock

from .settings_write import DashboardSettingsWriter


class DashboardService:
    """CLI-facing capability: settings + render + compose up/down."""

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
        docker: Optional[DockerStack] = None,
        writer: Optional[DashboardSettingsWriter] = None,
    ) -> None:
        self._stack = stack
        self._orch = orchestrator or Orchestrator(stack)
        self._docker = docker or DockerStack(stack, Shell(stack.root))
        self._writer = writer or DashboardSettingsWriter(stack.root)

    def status(self) -> Dict[str, Any]:
        return self._writer.status_public()

    def enable(
        self,
        *,
        public_host: Optional[str] = None,
        tls: Optional[str] = None,
        auth_mode: Optional[str] = None,
        verify_url: Optional[str] = None,
        sign_in_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        kwargs = {}
        if public_host is not None:
            kwargs["public_host"] = public_host
        if tls is not None:
            kwargs["tls"] = tls
        if auth_mode is not None:
            kwargs["auth_mode"] = auth_mode
        if verify_url is not None:
            kwargs["verify_url"] = verify_url
        if sign_in_url is not None:
            kwargs["sign_in_url"] = sign_in_url
        self._writer.enable(**kwargs)
        with StackLock(self._stack.root):
            self._orch.render()
            self._docker.start_stack([DASHBOARD_SERVICE_NAME])
            # Render may have reloaded router before this service existed; reload
            # again so Compose DNS for raft-dashboard resolves into upstreams.
            if self._stack.router in self._docker.running_services():
                self._docker.reload_router_nginx()
            self._ensure_acme()
        return self.status()

    def _ensure_acme(self) -> None:
        AcmeEnsure(
            self._stack,
            installer=AcmeGateInstall(self._stack, self._docker),
        ).run([DASHBOARD_SERVICE_NAME])

    def disable(self) -> Dict[str, Any]:
        self._writer.disable()
        with StackLock(self._stack.root):
            self._orch.render()
            self._docker.stop_service(DASHBOARD_SERVICE_NAME)
        return self.status()

    def set_password(self, password: str) -> Dict[str, Any]:
        self._writer.set_password(password)
        return self.status()
