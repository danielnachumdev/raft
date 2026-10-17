"""Fire component: ``raft github …`` (OAuth assist + deploy, not deploy keys)."""

import json as json_lib
from typing import Any, Dict, Optional

import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.platform.github import GithubAssistService


class GithubCLI:
    """GitHub OAuth assist / deploy (same ``GithubAssistService`` as serve).

    For private ``raft apply --git`` without OAuth, keep using ``raft auth``
    deploy keys — a different path.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        assist: Optional[GithubAssistService] = None,
        port: int = 8787,
    ) -> None:
        self._stack = stack
        self._port = port
        self._assist = assist or GithubAssistService(stack, port=port)

    def session(self, json: bool = False) -> None:
        """Show OAuth config status + connected accounts."""
        self._emit(self._assist.session(port=self._port), as_json=json)

    def config_show(self, json: bool = False) -> None:
        """Show public GitHub OAuth client config (secret redacted)."""
        self._emit(self._assist.config(port=self._port), as_json=json)

    def config_save(
        self, client_id: str = "", client_secret: str = ""
    ) -> None:
        """Save ``github.clientId`` / ``clientSecret`` into settings.yaml."""
        out = self._assist.save_config(
            client_id=client_id or None, client_secret=client_secret or None
        )
        OperatorSay.say("Saved GitHub OAuth config.")
        self._emit(out, as_json=True)

    def login(self, add: bool = False, port: int = 8787, mock: bool = False) -> None:
        """Print authorize URL, or complete mock login when ``github.mock`` is on.

        Example::

            raft github login --mock
            raft github login --port=8787
        """
        if mock or self._assist.session().get("mock"):
            self._finish_mock_login(add=add)
            return
        self._print_authorize_url(port=port, add=add)

    def _finish_mock_login(self, *, add: bool) -> None:
        out = self._assist.complete_mock(add=add)
        OperatorSay.say(
            f"Mock GitHub login complete ({out['account'].get('login')})."
        )

    def _print_authorize_url(self, *, port: int, add: bool) -> None:
        url = self._assist.login_url(port=port, add=add)
        OperatorSay.say(f"Open this URL in a browser:\n{url}")
        OperatorSay.say(
            "After GitHub redirects to the serve callback "
            "(or `raft github complete --code … --state …`), "
            "run `raft github session`."
        )

    def complete(self, code: str, state: str) -> None:
        """Finish a real OAuth exchange (same path as serve callback)."""
        out = self._assist.complete_oauth(code=code, state=state)
        OperatorSay.say(
            f"Logged in as {out['account'].get('login')}."
        )

    def accounts(self, json: bool = False) -> None:
        """List connected GitHub accounts."""
        snap = self._assist.session()
        if json:
            self._emit(
                {
                    "accounts": snap.get("accounts") or [],
                    "active_account_id": snap.get("active_account_id"),
                },
                as_json=True,
            )
            return
        self._print_accounts(snap)

    def _print_accounts(self, snap: Dict[str, Any]) -> None:
        rows = list(snap.get("accounts") or [])
        if not rows:
            OperatorSay.say(
                "No GitHub accounts. Use `raft github login` "
                "(or serve Add from GitHub)."
            )
            return
        active = snap.get("active_account_id")
        for row in rows:
            mark = "*" if row.get("id") == active else " "
            OperatorSay.say(
                f"{mark} {row.get('id')}  {row.get('login')}  "
                f"expired={row.get('expired')}"
            )

    def select(self, account_id: str) -> None:
        """Select the active browsing account."""
        try:
            self._assist.select_account(account_id)
        except KeyError as exc:
            raise OperatorError(
                f"GitHub account {account_id!r} not found.\n"
                f"Fix: raft github accounts",
                has_fix=False,
            ) from exc
        OperatorSay.say(f"Selected {account_id}.")

    def logout(self, account_id: str = "") -> None:
        """Delete one account id, or the active account when omitted."""
        if account_id:
            try:
                self._assist.delete_account(account_id)
            except KeyError as exc:
                raise OperatorError(
                    f"GitHub account {account_id!r} not found.\n"
                    f"Fix: raft github accounts",
                    has_fix=False,
                ) from exc
            OperatorSay.say(f"Deleted account {account_id}.")
            return
        self._assist.logout_active()
        OperatorSay.say("Deleted active GitHub account.")

    def repos(self, query: str = "", json: bool = False) -> None:
        """List repos visible to the active account."""
        payload = self._assist.repos(query=query)
        if json:
            self._emit(payload, as_json=True)
            return
        rows = list(payload.get("repos") or [])
        if not rows:
            OperatorSay.say("No repos matched.")
            return
        for row in rows:
            priv = "private" if row.get("private") else "public"
            OperatorSay.say(
                f"{row.get('full_name')}  {priv}  "
                f"default={row.get('default_branch')}"
            )

    def deploy(self, full_name: str, ref: str = "", json: bool = False) -> None:
        """Start a deploy-assist job for ``owner/repo`` (mock fixtures OK)."""
        job = self._assist.start_deploy(full_name=full_name, ref=ref)
        if json:
            self._emit(job, as_json=True)
            return
        OperatorSay.say(
            f"Deploy job {job.get('id')} status={job.get('status')} "
            f"app={job.get('app_name') or '-'}"
        )
        OperatorSay.say(
            f"Poll: raft github deploy_status {job.get('id')}"
        )

    def deploy_status(self, job_id: str, json: bool = False) -> None:
        """Show deploy-assist job status."""
        try:
            job = self._assist.deploy_status(job_id)
        except KeyError as exc:
            raise OperatorError(
                f"deploy job {job_id!r} not found.\n"
                f"Fix: start with raft github deploy owner/repo",
                has_fix=False,
            ) from exc
        self._emit(job, as_json=json)

    def _emit(self, payload: Dict[str, Any], *, as_json: bool) -> None:
        if as_json:
            OperatorSay.say(json_lib.dumps(payload, indent=2, sort_keys=False))
            return
        OperatorSay.say(yaml.safe_dump(payload, sort_keys=False).rstrip())
