"""Fire component: ``raft dashboard oauth …``."""

import json as json_lib
import sys
from pathlib import Path
from typing import Optional

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.lifecycle.dashboard.oauth_ops import DashboardOAuthOps


class DashboardOauthCLI:
    """Init secrets template + allowlist for ``auth.mode: oauth``."""

    def __init__(
        self,
        stack: Stack,
        *,
        ops: Optional[DashboardOAuthOps] = None,
    ) -> None:
        self._ops = ops or DashboardOAuthOps(stack.root)

    def init(
        self,
        provider: str = "google",
        issuer_url: Optional[str] = None,
        json: bool = False,
    ) -> None:
        """Write oauth.env template + empty allowlist; print redirect URL."""
        out = self._ops.init(provider=provider, issuer_url=issuer_url)
        if json:
            OperatorSay.say(json_lib.dumps(out, indent=2, sort_keys=True))
            return
        OperatorSay.say(f"provider: {out['provider']}")
        OperatorSay.say(f"env: {out['envFile']}")
        OperatorSay.say(f"allowlist: {out['allowlistFile']}")
        OperatorSay.say(f"redirect URL: {out['redirectUrl']}", style="ok")
        OperatorSay.say(out["hint"])

    def allowlist_set(self, file: str) -> None:
        """Replace allowlist from a local file (one identity per line)."""
        out = self._ops.allowlist_set(Path(file))
        OperatorSay.say(
            f"allowlist updated ({out['count']} identities)",
            style="ok",
        )

    def allowlist_add(self, identity: str = "") -> None:
        """Append one identity (arg or single stdin line)."""
        text = identity.strip() if identity else sys.stdin.readline()
        out = self._ops.allowlist_add(text)
        OperatorSay.say(
            f"allowlist updated ({out['count']} identities)",
            style="ok",
        )
