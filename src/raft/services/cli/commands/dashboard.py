"""Fire component: ``raft dashboard …`` (always-on ops UI)."""

import getpass
import json as json_lib
from typing import Optional

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.lifecycle.dashboard.service import DashboardService


class DashboardCLI:
    """Manage the always-on ``raft-dashboard`` Compose service."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[DashboardService] = None,
    ) -> None:
        self._stack = stack
        self._svc = service or DashboardService(stack)

    def status(self, json: bool = False) -> None:
        """Show enabled / port / public Host / auth mode."""
        payload = self._svc.status()
        if json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=True))
            return
        self._print_status(payload)

    def _print_status(self, payload: dict) -> None:
        enabled = "yes" if payload.get("enabled") else "no"
        OperatorSay.say(f"enabled: {enabled}")
        OperatorSay.say(f"port: {payload.get('port')}")
        OperatorSay.say(f"local: {payload.get('localUrl')}")
        public = payload.get("publicUrl") or "(none)"
        OperatorSay.say(f"public: {public}")
        auth = payload.get("auth") or {}
        OperatorSay.say(f"auth.mode: {auth.get('mode')}")
        OperatorSay.say(f"tls: {payload.get('tls')}")

    def enable(
        self,
        public_host: Optional[str] = None,
        tls: Optional[str] = None,
        auth_mode: Optional[str] = None,
        verify_url: Optional[str] = None,
        sign_in_url: Optional[str] = None,
    ) -> None:
        """Enable always-on dashboard (render + compose up)."""
        self._svc.enable(
            public_host=public_host,
            tls=tls,
            auth_mode=auth_mode,
            verify_url=verify_url,
            sign_in_url=sign_in_url,
        )
        payload = self._svc.status()
        OperatorSay.say(
            f"raft-dashboard enabled on {payload.get('localUrl')}",
            style="ok",
        )
        if payload.get("publicUrl"):
            OperatorSay.say(f"public URL: {payload['publicUrl']}", style="ok")

    def disable(self) -> None:
        """Disable always-on dashboard (render + compose stop)."""
        self._svc.disable()
        OperatorSay.say("raft-dashboard disabled", style="ok")

    def set_password(self, password: Optional[str] = None) -> None:
        """Set password hash for ``auth.mode: password`` (prompt if omitted)."""
        secret = password if password is not None else getpass.getpass(
            "Dashboard password: "
        )
        self._svc.set_password(secret)
        OperatorSay.say("dashboard password hash updated", style="ok")
