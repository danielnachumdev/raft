"""E2E: rendered apps Compose runs and containers behave as intended."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from tests.e2e.shared.compose import ComposeProject
from tests.shared.http import HttpClient, tcp_connect

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("compose_project", ["http_only"], indirect=True)
class TestE2ESingleHttp:
    def test_e2e_single_http_echo(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, _vol = compose_project
        cp.wait_running("http-only")
        port = cp.published_port("http-only", 5678)
        assert port is not None
        status, _body = HttpClient(f"http://127.0.0.1:{port}").get("/")
        assert status == 200


@pytest.mark.parametrize("compose_project", ["expose_none_volume"], indirect=True)
class TestE2EExposeNoneAndVolume:
    def test_e2e_expose_none_not_published(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, _vol = compose_project
        cp.wait_running("demo-expose-none-vol")
        raw = (_home / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert '"6379:6379"' not in raw and "6379:6379" not in raw
        port = cp.published_port("demo-expose-none-vol", 6379)
        assert port is not None
        assert tcp_connect("127.0.0.1", port)

    def test_e2e_volume_bind(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, vol = compose_project
        cp.wait_running("demo-expose-none-vol")
        assert (vol / "raft-e2e-marker.txt").is_file()
        proc = self._exec_cat(cp)
        assert "from-host" in proc.stdout

    def _exec_cat(self, cp: ComposeProject):
        return subprocess.run(
            [
                "docker", "compose", "-p", cp.project, "-f", str(cp.compose_file),
                "exec", "-T", "demo-expose-none-vol", "cat", "/data/raft-e2e-marker.txt",
            ],
            check=True, cwd=cp.workdir, capture_output=True, text=True, timeout=30,
        )


@pytest.mark.parametrize("compose_project", ["multi_app_group"], indirect=True)
class TestE2EMultiApp:
    def test_e2e_depends_on_order(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, home, _vol = compose_project
        apps = (home / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "demo-stack-redis:" in apps
        assert "condition: service_started" in apps
        cp.wait_running("demo-stack-redis")
        cp.wait_running("demo-stack-front")

    def test_e2e_multi_app_same_project(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, _vol = compose_project
        cp.wait_running("demo-stack-redis")
        cp.wait_running("demo-stack-front")
        last = self._try_getent(cp)
        assert cp.service_running("demo-stack-redis")
        assert cp.service_running("demo-stack-front"), last

    def _try_getent(self, cp: ComposeProject) -> str:
        deadline = time.time() + 30
        last = ""
        while time.time() < deadline:
            proc = subprocess.run(
                [
                    "docker", "compose", "-p", cp.project, "-f", str(cp.compose_file),
                    "exec", "-T", "demo-stack-front", "getent", "hosts", "demo-stack-redis",
                ],
                check=False, cwd=cp.workdir, capture_output=True, text=True, timeout=30,
            )
            last = proc.stdout + proc.stderr
            if proc.returncode == 0 and "demo-stack-redis" in last:
                return last
            time.sleep(0.5)
        return last
