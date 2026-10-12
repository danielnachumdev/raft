"""Shared DomainTestCase for apply/deploy/ops/auth/sync unit tests."""

from pathlib import Path
from unittest.mock import MagicMock

from raft.auth import GitAuthManager
from raft.deploy.cutover import CutoverSession
from raft.deploy.orchestrator import Orchestrator

from .base import AppliedInventory, AppliedStackCase, StackMakers


class DomainTestCase(AppliedStackCase):
    def orchestrator(self, *, mock_deps: bool = True) -> Orchestrator:
        orch = Orchestrator(self.stack)
        if mock_deps:
            orch.docker = MagicMock()
            orch.nginx = MagicMock()
            orch.http = MagicMock()
            orch.syncer = MagicMock()
        return orch

    @staticmethod
    def stub_http_ready(
        http: MagicMock,
        *,
        public_host_ok: bool = True,
        tcp_port_ok: bool = True,
    ) -> MagicMock:
        http.public_host_ok.return_value = public_host_ok
        http.tcp_port_ok.return_value = tcp_port_ok
        return http

    def cutover_session(self) -> CutoverSession:
        AppliedInventory.write_applied_app(
            self.tmp_path, "app", extra=self._short_readiness()
        )
        stack = StackMakers.make_local_stack(
            self.tmp_path, drain_seconds=0.0, ready_timeout_seconds=1.0
        )
        return CutoverSession(
            stack=stack,
            app=stack.apps[0],
            docker=MagicMock(),
            nginx=MagicMock(),
            http=MagicMock(),
        )

    @staticmethod
    def _short_readiness() -> dict:
        return {
            "readiness": {
                "type": "http",
                "port": "http",
                "timeoutSeconds": 1,
                "startPeriodSeconds": 0.25,
                "intervalSeconds": 0.25,
                "retries": 1,
            },
        }

    def auth_manager(self, **git_stack_kwargs) -> GitAuthManager:
        stack = StackMakers.make_git_stack(self.tmp_path, **git_stack_kwargs)
        mgr = GitAuthManager(stack)
        mgr.sh = self.shell
        return mgr

    @staticmethod
    def write_keypair(mgr: GitAuthManager, service: str) -> None:
        mgr.keys_dir.mkdir(parents=True, exist_ok=True)
        mgr.key_path(service).write_text("PRIVATE", encoding="utf-8")
        mgr.pub_path(service).write_text("ssh-ed25519 AAAA test\n", encoding="utf-8")

    def fake_ssh_keygen(self):
        def run(args, **kwargs):
            if args and args[0] == "ssh-keygen":
                key = Path(args[args.index("-f") + 1])
                key.parent.mkdir(parents=True, exist_ok=True)
                key.write_text("PRIVATE", encoding="utf-8")
                Path(str(key) + ".pub").write_text(
                    "ssh-ed25519 AAAA setup\n", encoding="utf-8"
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        return run
