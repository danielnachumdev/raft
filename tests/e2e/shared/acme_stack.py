"""Real-Docker harness: tls: acme issue/renew via Pebble against the gate."""

from __future__ import annotations

import hashlib
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import yaml

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.models.stack import load_stack
from raft.models.state.scaling_store import ScalingStore
from raft.services.acme.ensure import AcmeEnsure
from raft.services.acme.install import AcmeGateInstall
from raft.services.acme.paths import AcmePaths
from raft.services.render import StackRenderer
from tests.e2e.shared.compose import new_project_name
from tests.e2e.shared.pebble_side import PebbleSide, pebble_services
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.e2e.shared.scale_stack import _gate_volumes, _router_service
from tests.shared.artifacts import GeneratedArtifacts
from tests.shared.http import HttpClient
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.wait import Wait
from tests.shared.yaml_doc import YamlDoc

APP = "http-only"
PUBLIC_HOST = "acme.raft.test"
SCALING = {"idleSeconds": 3600, "wakeTimeoutSeconds": 120, "minUpSeconds": 1}


class AcmeE2EStack:
    """Gate + router + app + Pebble; host-side AcmeEnsure with Pebble trust."""

    def __init__(
        self,
        home: Path,
        project: str,
        docker: DockerStack,
        pebble: PebbleSide,
        gate_http: int,
        gate_https: int,
    ) -> None:
        self.home = home
        self.project = project
        self.docker = docker
        self.pebble = pebble
        self.gate_http = gate_http
        self.gate_https = gate_https
        self.store = ScalingStore(home)
        self.http = HttpClient(f"http://127.0.0.1:{gate_http}")

    @classmethod
    def create(cls, home: Path) -> "AcmeE2EStack":
        project = new_project_name()
        cls._prepare_home(home)
        model = load_stack(home)
        # load_stack re-copies product compose; install e2e compose after.
        PebbleSide(home, DockerStack(model, Shell(home))).write_config(http_port=80)
        cls._install_compose(home, project)
        docker = DockerStack(model, Shell(home))
        pebble = PebbleSide(home, docker)
        docker.sh.compose("up", "-d", "--pull", "missing", check=True, capture=True)
        gate_http = cls._wait_port(docker, "raft-gate", 80)
        gate_https = cls._wait_port(docker, "raft-gate", 443)
        cls._wait_gate_http(gate_http)
        pebble.ready()
        cls._write_acme_settings(home, pebble.directory_url)
        stack = cls(home, project, docker, pebble, gate_http, gate_https)
        stack.wait_app_running()
        return stack

    @staticmethod
    def _wait_gate_http(host_port: int) -> None:
        """Docker can publish :80 before nginx workers are accepting."""

        def ready() -> bool:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{host_port}/", timeout=1)
                return True
            except urllib.error.HTTPError:
                return True  # any HTTP response ⇒ listening
            except OSError:
                return False

        Wait.until(ready, timeout=60.0, message="gate nginx not accepting HTTP")

    def close(self) -> None:
        self.docker.stop_stack()

    def __enter__(self) -> "AcmeE2EStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def wait_app_running(self, *, timeout: float = 60.0) -> None:
        ServiceRuntimeWait(self.docker, APP).until_running(timeout=timeout)

    def wait_app_stopped(self, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, APP).until_stopped(timeout=timeout)

    def scale_to_zero(self) -> None:
        self.docker.stop_service(APP)
        self.store.mark_scaled_to_zero(APP)
        self.wait_app_stopped()

    def ensure_acme(self) -> None:
        prev_trust = {key: os.environ.get(key) for key in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE")}
        os.environ.update(self.pebble.trust_env())
        try:
            # Do not load_stack here — it re-copies product compose.yaml over the
            # e2e project (gate/pebble services) and breaks compose exec/reload.
            stack = self.docker.stack
            AcmeEnsure(
                stack,
                installer=AcmeGateInstall(stack, self.docker),
            ).run([APP])
        finally:
            self._restore_trust_env(prev_trust)
        assert AcmePaths(self.home).live_material_present(APP), self._acme_error()

    @staticmethod
    def _restore_trust_env(prev: dict) -> None:
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def force_renew_window(self) -> None:
        YamlDoc(self.home / "settings.yaml").merge_root(
            "acme",
            {
                "email": "raft-e2e@example.com",
                "directory": self.pebble.directory_url,
                "renewDaysBeforeExpiry": 9999,
                "challenge": "http-01",
            },
        )
        # Drop live PEMs so ensure re-issues. Pebble often rejects a second
        # order against the same authz ("challenge … status valid").
        pem, key = AcmePaths(self.home).cert_files(APP)
        pem.unlink(missing_ok=True)
        key.unlink(missing_ok=True)

    def pem_digest(self) -> str:
        pem = (self.home / "certs" / APP / "acme.pem").read_bytes()
        return hashlib.sha256(pem).hexdigest()

    def assert_challenge_token(self, token: str, body: str) -> None:
        webroot = self.home / "state" / "acme" / "http-01"
        webroot.mkdir(parents=True, exist_ok=True)
        (webroot / token).write_text(body, encoding="utf-8")
        resp = self.http.get(
            f"/.well-known/acme-challenge/{token}",
            host=PUBLIC_HOST,
            expect_status=200,
        )
        assert resp.body.strip() == body

    def assert_https_ok(self) -> None:
        cmd = [
            "curl",
            "-fsS",
            "--max-time",
            "5",
            "--cacert",
            str(self.pebble.root_ca),
            "--resolve",
            f"{PUBLIC_HOST}:{self.gate_https}:127.0.0.1",
            f"https://{PUBLIC_HOST}:{self.gate_https}/",
        ]
        Wait.until(
            lambda: subprocess.run(cmd, capture_output=True, text=True).returncode == 0,
            timeout=60.0,
            message="HTTPS via gate with Pebble CA failed",
        )

    def _acme_error(self) -> str:
        path = self.home / "state" / "acme" / "apps" / f"{APP}.json"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return "no acme app state"

    @classmethod
    def _prepare_home(cls, home: Path) -> None:
        RaftHomeFixtures.apply_and_render(
            home, RaftHomeFixtures.fixture_app_yamls("http_only")
        )
        YamlDoc(home / "state" / "apps" / f"{APP}.yaml").merge_spec(
            {"tls": "acme", "publicHost": PUBLIC_HOST, "scaling": dict(SCALING)}
        )
        StackRenderer(load_stack(home)).render()
        (home / "state" / "acme" / "http-01").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_acme_settings(home: Path, directory: str) -> None:
        YamlDoc(home / "settings.yaml").merge_root(
            "acme",
            {
                "email": "raft-e2e@example.com",
                "directory": directory,
                "renewDaysBeforeExpiry": 30,
                "challenge": "http-01",
            },
        )

    @staticmethod
    def _install_compose(home: Path, project: str) -> None:
        apps = GeneratedArtifacts.under(home).compose_apps()
        services = dict(apps.get("services") or {})
        services.pop("router", None)
        services.update(_edge_and_pebble())
        doc = {"name": project, "services": services}
        (home / "compose.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
        )

    @staticmethod
    def _wait_port(docker: DockerStack, service: str, port: int) -> int:
        published: Optional[int] = None

        def ready() -> bool:
            nonlocal published
            result = docker.sh.compose(
                "port", service, str(port), capture=True, check=False
            )
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out:
                published = int(out.rsplit(":", 1)[-1])
                return True
            return False

        Wait.until(ready, timeout=60.0, message=f"{service}:{port} not published")
        assert published is not None
        return published


def _edge_and_pebble() -> dict:
    gate = {
        "image": "nginx:alpine",
        "ports": ["127.0.0.1::80", "127.0.0.1::443"],
        "extra_hosts": ["raft-controller:host-gateway"],
        "volumes": _gate_volumes(),
    }
    out = {"raft-gate": gate, "raft-router": _router_service()}
    out.update(pebble_services())
    return out
