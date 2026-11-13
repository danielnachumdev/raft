"""Run GitHub-assist git auth + apply on the host via Docker one-shot."""

from __future__ import annotations

from typing import Optional

from raft.core.core.models.stack import Stack
from raft.core.platform.adapters.docker import HostOneshot, HostOneshotGate
from raft.core.platform.adapters.shell import Shell
from raft.core.platform.auth.manager import GitAuthManager


class GithubDeployHostGit:
    """Mint deploy key + ``raft apply --git`` as the operator on the host.

    Always-on dashboard lacks a real passwd row / reliable SSH home for
    OpenSSH; the host one-shot mounts operator ``HOME`` + ``/etc/passwd``.
    """

    _AUTH_TIMEOUT = 120.0
    _APPLY_TIMEOUT = 1800.0

    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        oneshot: Optional[HostOneshot] = None,
        gate: Optional[HostOneshotGate] = None,
    ) -> None:
        self._stack = stack
        self._shell = shell or Shell(stack.root)
        self._oneshot = oneshot or HostOneshot(self._shell)
        self._gate = gate or HostOneshotGate()

    def in_dashboard(self) -> bool:
        return self._gate.in_dashboard()

    def prepare_key(self, app_name: str, ssh_url: str) -> str:
        """Ensure deploy key on the host; return pasteable public key text."""
        self._gate.ensure()
        self._oneshot.run(
            self._auth_argv(app_name, ssh_url),
            timeout=self._AUTH_TIMEOUT,
            with_docker=False,
        )
        return GitAuthManager(self._stack).show_pubkey(app_name)

    def apply_git(self, ssh_url: str, *, ref: str, manifest_path: str) -> None:
        self._gate.ensure()
        self._oneshot.run(
            self._apply_argv(ssh_url, ref=ref, manifest_path=manifest_path),
            timeout=self._APPLY_TIMEOUT,
            with_docker=True,
        )

    @staticmethod
    def _auth_argv(app_name: str, ssh_url: str) -> list[str]:
        return ["raft", "auth", "setup", app_name, "--repo", ssh_url]

    @staticmethod
    def _apply_argv(ssh_url: str, *, ref: str, manifest_path: str) -> list[str]:
        argv: list[str] = [
            "raft",
            "apply",
            "--git",
            ssh_url,
            "--ref",
            ref,
        ]
        rel = (manifest_path or "").strip()
        if rel:
            argv.extend(["--manifest_path", rel])
        return argv
