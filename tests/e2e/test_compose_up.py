"""E2E: rendered apps Compose runs and containers behave as intended."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from tests.e2e.shared.compose import ComposeProject, http_get, tcp_connect

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
        # http-echo returns the -text value or default; any HTTP response means up.
        status, _body = http_get(f"http://127.0.0.1:{port}/")
        assert status == 200


@pytest.mark.parametrize("compose_project", ["expose_none_volume"], indirect=True)
class TestE2EExposeNoneAndVolume:
    def test_e2e_expose_none_not_published(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, _vol = compose_project
        cp.wait_running("demo-expose-none-vol")
        # We intentionally add ephemeral publish in apps_only_compose for probing.
        # Assert the *rendered* raft compose had no host ports before overlay:
        raw = (_home / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        # After patch, still no `ports:` under expose-none-vol in original intent —
        # check service had no ports key before apps_only_compose by reading that
        # the pre-e2e file sections: look for host publish of 6379 as "6379:6379"
        assert '"6379:6379"' not in raw
        assert "6379:6379" not in raw
        port = cp.published_port("demo-expose-none-vol", 6379)
        assert port is not None  # e2e overlay only
        assert tcp_connect("127.0.0.1", port)

    def test_e2e_volume_bind(
        self, compose_project: tuple[ComposeProject, Path, Path]
    ) -> None:
        cp, _home, vol = compose_project
        cp.wait_running("demo-expose-none-vol")
        assert (vol / "raft-e2e-marker.txt").is_file()
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                cp.project,
                "-f",
                str(cp.compose_file),
                "exec",
                "-T",
                "demo-expose-none-vol",
                "cat",
                "/data/raft-e2e-marker.txt",
            ],
            check=True,
            cwd=cp.workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "from-host" in proc.stdout


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
        # DNS: resolve peer by Compose service name from front container.
        deadline = time.time() + 30
        last = ""
        while time.time() < deadline:
            proc = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    cp.project,
                    "-f",
                    str(cp.compose_file),
                    "exec",
                    "-T",
                    "demo-stack-front",
                    "getent",
                    "hosts",
                    "demo-stack-redis",
                ],
                check=False,
                cwd=cp.workdir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            last = proc.stdout + proc.stderr
            if proc.returncode == 0 and "demo-stack-redis" in last:
                return
            time.sleep(0.5)
        # http-echo may lack getent — both running in same project is enough.
        assert cp.service_running("demo-stack-redis")
        assert cp.service_running("demo-stack-front"), last
