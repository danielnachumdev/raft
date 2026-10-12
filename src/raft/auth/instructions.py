"""Operator-facing deploy-key copy/paste instructions."""

from typing import Optional, Sequence

from ..ui import OperatorSay
from .strategies import DeployKeyHostHint, GenericDeployKeyHint, GithubDeployKeyHint
from .url import SshGitUrl


class DeployKeyInstructions:
    """Print title + pubkey + host-specific open CTAs."""

    def __init__(
        self,
        hints: Optional[Sequence[DeployKeyHostHint]] = None,
    ) -> None:
        self._hints = list(hints) if hints is not None else [
            GithubDeployKeyHint(),
            GenericDeployKeyHint(),
        ]

    @staticmethod
    def pubkey_for_paste(pubkey: str) -> str:
        parts = pubkey.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return pubkey

    def print_for_copy(
        self,
        service: str,
        *,
        host: str,
        repo_path: str,
        pubkey: str,
        title: str,
    ) -> None:
        OperatorSay.say(f"Add a read-only deploy key for {service}:", style="info")
        OperatorSay.say("")
        OperatorSay.say(f"  Title:  {title}")
        OperatorSay.say(f"  Key:    {self.pubkey_for_paste(pubkey)}")
        OperatorSay.say("")
        for line in self._hint_for(host).open_lines(host, repo_path):
            OperatorSay.say(line)

    def announce(
        self,
        service: str,
        *,
        host: str,
        parsed: SshGitUrl,
        pubkey: str,
        title: str,
    ) -> None:
        self.print_for_copy(
            service,
            host=host,
            repo_path=parsed.path,
            pubkey=pubkey,
            title=title,
        )

    def say_next_steps(self, service: str, repo_url: str, *, applied: bool) -> None:
        if applied:
            OperatorSay.say(f"next: raft auth test {service} && raft sync {service}", style="info")
            return
        OperatorSay.say(
            f"next: raft auth test {service} --repo {repo_url} "
            f"&& raft apply --git {repo_url}",
            style="info",
        )

    def _hint_for(self, host: str) -> DeployKeyHostHint:
        for hint in self._hints:
            if hint.matches(host):
                return hint
        return GenericDeployKeyHint()
