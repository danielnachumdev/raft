"""Apps-only Compose harness for operator CLI e2e stories (logs / serve)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.models.stack import load_stack
from raft.ops.logs import Logs
from raft.ops.status import Status
from raft.serve.app import ServeAppFactory
from tests.e2e.shared.compose import apps_only_compose, new_project_name
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.shared.http import HttpClient
from tests.shared.raft_home import RaftHomeFixtures


class OpsE2EStack:
    """Apply http_only, apps-only compose under a unique project name."""

    APP = "http-only"
    FIXTURE = "http_only"
    CONTAINER_PORT = 5678

    def __init__(self, home: Path, project: str, docker: DockerStack) -> None:
        self.home = home
        self.project = project
        self.docker = docker
        self.stack = docker.stack

    @classmethod
    def create(cls, home: Path) -> "OpsE2EStack":
        project = new_project_name()
        RaftHomeFixtures.apply_and_render(home, RaftHomeFixtures.fixture_app_yamls(cls.FIXTURE))
        model = load_stack(home)
        cls._install_apps_compose(home, project)
        docker = DockerStack(model, Shell(home))
        stack = cls(home, project, docker)
        stack._compose_up()
        stack.wait_running()
        return stack

    def wait_running(self, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, self.APP).until_running(timeout=timeout)

    def published_port(self) -> int:
        result = self.docker.sh.compose(
            "port", self.APP, str(self.CONTAINER_PORT), capture=True, check=True
        )
        hostport = (result.stdout or "").strip().rsplit(":", 1)[-1]
        return int(hostport)

    def hit_app(self) -> None:
        HttpClient(f"http://127.0.0.1:{self.published_port()}").get("/")

    def snapshot_logs(self, *names: str, tail: int = 50) -> str:
        out = StringIO()
        Logs(self.stack).show(*(names or (self.APP,)), tail=tail, out=out)
        return out.getvalue()

    def serve_client(self) -> TestClient:
        return TestClient(ServeAppFactory(self.stack, status=Status(self.stack)).create())

    def close(self) -> None:
        self.docker.stop_stack()

    def __enter__(self) -> "OpsE2EStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _compose_up(self) -> None:
        self.docker.sh.compose("up", "-d", "--pull", "missing", check=True, capture=True)

    @staticmethod
    def _install_apps_compose(home: Path, project: str) -> None:
        generated = home / "generated"
        scratch = generated / "compose.e2e.yaml"
        apps_only_compose(generated, scratch)
        doc = yaml.safe_load(scratch.read_text(encoding="utf-8")) or {}
        doc["name"] = project
        (home / "compose.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
