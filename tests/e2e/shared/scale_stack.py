"""Real-Docker harness: gate holding page + wake for scaled apps."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.controller.scale import Scaler
from raft.controller.scaling_store import ScalingStore
from raft.controller.wake_http import start_wake_http
from raft.models.stack import load_stack
from raft.services.render import StackRenderer
from tests.e2e.shared.compose import new_project_name
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.shared.artifacts import GeneratedArtifacts
from tests.shared.http import HttpClient, HttpResponse
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.wait import Wait
from tests.shared.yaml_doc import YamlDoc

APP = "http-only"
PUBLIC_HOST = "site.test"
SCALING = {
    "idleSeconds": 3600,
    "wakeTimeoutSeconds": 60,
    "minUpSeconds": 1,
}


class ScaleE2EStack:
    """Gate + router + app compose; wake API on the host (host-gateway)."""

    def __init__(
        self,
        home: Path,
        project: str,
        docker: DockerStack,
        scaler: Scaler,
        wake_port: int,
        gate_port: int,
    ) -> None:
        self.home = home
        self.project = project
        self.docker = docker
        self.scaler = scaler
        self.wake_port = wake_port
        self.gate_port = gate_port
        self.store = ScalingStore(home)
        self._wake = None
        self.http = HttpClient(f"http://127.0.0.1:{gate_port}")

    @classmethod
    def create(cls, home: Path) -> "ScaleE2EStack":
        project = new_project_name()
        cls._prepare_home(home)
        model = load_stack(home)
        docker = DockerStack(model, Shell(home))
        scaler = Scaler(home, docker)
        wake = start_wake_http(scaler, host="0.0.0.0", port=0)
        assert wake._httpd is not None
        wake_port = int(wake._httpd.server_address[1])
        cls._rewrite_wake_port(home, wake_port)
        # load_stack re-copies product compose; install edge compose after.
        cls._install_edge_compose(home, project)
        docker.sh.compose("up", "-d", "--pull", "missing", check=True, capture=True)
        gate_port = cls._wait_gate_port(docker, timeout=60.0)
        stack = cls(home, project, docker, scaler, wake_port, gate_port)
        stack._wake = wake
        stack.wait_app_running()
        stack.wait_live()
        return stack

    @classmethod
    def _prepare_home(cls, home: Path) -> None:
        RaftHomeFixtures.apply_and_render(home, RaftHomeFixtures.fixture_app_yamls("http_only"))
        cls._inject_scaling(home)
        StackRenderer(load_stack(home)).render()

    def close(self) -> None:
        if self._wake is not None:
            self._wake.stop()
        self.docker.stop_stack()

    def __enter__(self) -> "ScaleE2EStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def wait_app_running(self, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, APP).until_running(timeout=timeout)

    def wait_live(self, *, timeout: float = 45.0) -> None:
        Wait.until(
            self._is_live_body,
            timeout=timeout,
            message="gate Host path not live",
        )

    def _is_live_body(self) -> bool:
        resp = self.curl_host(expect_status=None)
        return resp.status == 200 and "Starting" not in resp.body and "Unavailable" not in resp.body

    def wait_app_stopped(self, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, APP).until_stopped(timeout=timeout)

    def curl_host(self, *, expect_status: Optional[int] = 200) -> HttpResponse:
        return self.http.get("/", host=PUBLIC_HOST, expect_status=expect_status)

    def scale_to_zero(self) -> None:
        self.docker.stop_service(APP)
        self.store.mark_scaled_to_zero(APP)
        self.wait_app_stopped()

    @staticmethod
    def _inject_scaling(home: Path) -> None:
        YamlDoc(home / "state" / "apps" / f"{APP}.yaml").merge_spec({"scaling": dict(SCALING)})

    @staticmethod
    def _rewrite_wake_port(home: Path, port: int) -> None:
        path = home / "generated" / "nginx" / "gate-http" / "listeners.conf"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("raft-controller:8090", f"raft-controller:{port}"),
            encoding="utf-8",
        )

    @staticmethod
    def _install_edge_compose(home: Path, project: str) -> None:
        apps = GeneratedArtifacts.under(home).compose_apps()
        services = dict(apps.get("services") or {})
        services.pop("router", None)
        services.update(_edge_services())
        doc = {"name": project, "services": services}
        (home / "compose.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _wait_gate_port(docker: DockerStack, *, timeout: float) -> int:
        port: Optional[int] = None

        def ready() -> bool:
            nonlocal port
            result = docker.sh.compose("port", "raft-gate", "80", capture=True, check=False)
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out:
                port = int(out.rsplit(":", 1)[-1])
                return True
            return False

        Wait.until(ready, timeout=timeout, message="raft-gate port not published")
        assert port is not None
        return port


def _edge_services() -> dict:
    return {"raft-gate": _gate_service(), "raft-router": _router_service()}


def _gate_service() -> dict:
    return {
        "image": "nginx:alpine",
        "ports": ["127.0.0.1::80"],
        "extra_hosts": ["raft-controller:host-gateway"],
        "volumes": _gate_volumes(),
    }


def _gate_volumes() -> list:
    return [
        "./nginx/gate/nginx.conf:/etc/nginx/nginx.conf:ro",
        "./nginx/gate/proxy_router.inc:/etc/nginx/gate/proxy_router.inc:ro",
        "./generated/nginx/gate-http:/etc/nginx/http-generated:ro",
        "./generated/nginx/gate-stream:/etc/nginx/stream-generated:ro",
        "./generated/nginx/gate-tls:/etc/nginx/gate-tls:ro",
        "./nginx/errors:/usr/share/nginx/errors:ro",
        "./certs:/etc/nginx/certs:ro",
        "./state/scaling/markers:/etc/nginx/scaling/markers:ro",
    ]


def _router_service() -> dict:
    return {
        "image": "nginx:alpine",
        "expose": ["80"],
        "volumes": [
            "./nginx/router/default.conf:/etc/nginx/conf.d/default.conf:ro",
            "./generated/nginx/router:/etc/nginx/router-generated:ro",
            "./generated/nginx/upstreams:/etc/nginx/upstreams:ro",
            "./nginx/errors:/usr/share/nginx/errors:ro",
        ],
    }
