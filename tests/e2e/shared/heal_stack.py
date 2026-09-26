"""Real-Docker harness for controller heal e2e (apps-only Compose project)."""

from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer
from raft.models.stack import load_stack

from tests.e2e.shared.compose import apps_only_compose, new_project_name
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.yaml_doc import YamlDoc

# Fast CI knobs (Healer.tick(now=…) bypasses wall-clock interval sleep).
HEAL_INTERVAL_SECONDS = 1.0
HEAL_FAIL_THRESHOLD = 1
HEAL_COOLDOWN_SECONDS = 0.0
HEAL_MAX_RESTARTS = 1
HEAL_ESCALATE_AFTER = 1


class HealE2EStack:
    """Apply http_only, apps-only compose under a unique project, run Healer."""

    APP = "http-only"
    FIXTURE = "http_only"

    def __init__(
        self,
        home: Path,
        project: str,
        docker: DockerStack,
        healer: Healer,
        deploy_calls: List[str],
    ) -> None:
        self.home = home
        self.project = project
        self.docker = docker
        self.healer = healer
        self.deploy_calls = deploy_calls

    @classmethod
    def create(cls, home: Path) -> "HealE2EStack":
        project = new_project_name()
        RaftHomeFixtures.apply_and_render(
            home, RaftHomeFixtures.fixture_app_yamls(cls.FIXTURE)
        )
        cls._write_heal_settings(home)
        # load_stack → ensure_raft_home re-copies product compose.yaml; install after.
        model = load_stack(home)
        cls._install_apps_compose(home, project)
        deploy_calls: List[str] = []
        docker = DockerStack(model, Shell(home))
        healer = Healer(
            home, cls._fast_healing(), docker, deploy=deploy_calls.append
        )
        stack = cls(home, project, docker, healer, deploy_calls)
        stack._compose_up()
        stack.wait_runtime("running")
        return stack

    def _compose_up(self) -> None:
        self.docker.sh.compose(
            "up", "-d", "--pull", "missing", check=True, capture=True
        )

    def close(self) -> None:
        self.docker.stop_stack()

    def __enter__(self) -> "HealE2EStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def stop_app(self) -> None:
        self.docker.sh.compose("stop", self.APP, check=True, capture=True)
        self.wait_not_running()

    def wait_not_running(self, *, timeout: float = 45.0) -> None:
        """Compose ``ps -q`` hides stopped containers → raft sees ``missing``."""
        ServiceRuntimeWait(self.docker, self.APP).until_stopped(
            timeout=timeout,
            message=(
                f"{self.APP} still running "
                f"(project={self.project})"
            ),
        )

    def wait_runtime(self, status: str, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, self.APP).until_status(
            status,
            timeout=timeout,
            message=(
                f"{self.APP} wanted status={status!r} "
                f"(project={self.project})"
            ),
        )

    @staticmethod
    def _fast_healing() -> HealingConfig:
        return HealingConfig(
            enabled=True,
            interval_seconds=HEAL_INTERVAL_SECONDS,
            fail_threshold=HEAL_FAIL_THRESHOLD,
            cooldown_seconds=HEAL_COOLDOWN_SECONDS,
            max_restarts=HEAL_MAX_RESTARTS,
            escalate_after_restarts=HEAL_ESCALATE_AFTER,
        )

    @staticmethod
    def _write_heal_settings(home: Path) -> None:
        YamlDoc(home / "settings.yaml").merge_root(
            "healing",
            {
                "enabled": True,
                "intervalSeconds": HEAL_INTERVAL_SECONDS,
                "failThreshold": HEAL_FAIL_THRESHOLD,
                "cooldownSeconds": HEAL_COOLDOWN_SECONDS,
                "maxRestarts": HEAL_MAX_RESTARTS,
                "escalateAfterRestarts": HEAL_ESCALATE_AFTER,
            },
        )

    @staticmethod
    def _install_apps_compose(home: Path, project: str) -> None:
        generated = home / "generated"
        scratch = generated / "compose.e2e.yaml"
        apps_only_compose(generated, scratch)
        doc = yaml.safe_load(scratch.read_text(encoding="utf-8")) or {}
        doc["name"] = project
        (home / "compose.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
        )
