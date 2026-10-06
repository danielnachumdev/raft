"""Pebble + challtestsrv helpers for ACME e2e (Docker network HTTP-01)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from pathlib import Path

from raft.adapters.docker import DockerStack
from tests.shared.http import HttpClient
from tests.shared.wait import Wait

PEBBLE_IMAGE = "ghcr.io/letsencrypt/pebble:latest"
CHALLTEST_IMAGE = "ghcr.io/letsencrypt/pebble-challtestsrv:latest"
PEBBLE_SVC = "raft-pebble"
CHALLTEST_SVC = "raft-challtestsrv"


class PebbleSide:
    """Configure Pebble HTTP-01 against the gate; expose directory + trust roots."""

    def __init__(self, home: Path, docker: DockerStack) -> None:
        self.home = home
        self.docker = docker
        self.minica = home / "pebble.minica.pem"
        self.root_ca = home / "pebble-root.pem"
        self.directory_url = ""
        self._mgmt_base = ""

    def write_config(self, *, http_port: int = 80) -> Path:
        path = self.home / "pebble-e2e.json"
        path.write_text(json.dumps(self._config(http_port), indent=2) + "\n", encoding="utf-8")
        return path

    def ready(self) -> None:
        self._extract_minica()
        acme_port = self._published(PEBBLE_SVC, 14000)
        mgmt_port = self._published(PEBBLE_SVC, 15000)
        self.directory_url = f"https://127.0.0.1:{acme_port}/dir"
        self._mgmt_base = f"https://127.0.0.1:{mgmt_port}"
        Wait.until(self._directory_ok, timeout=60.0, message="pebble /dir not ready")
        self._point_dns_at_gate()
        self._fetch_root()

    def trust_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["REQUESTS_CA_BUNDLE"] = str(self.minica)
        env["SSL_CERT_FILE"] = str(self.minica)
        return env

    def ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=str(self.root_ca))

    def _point_dns_at_gate(self) -> None:
        gate_ip = self._container_ip("raft-gate")
        mgmt = self._published(CHALLTEST_SVC, 8055)
        client = HttpClient(f"http://127.0.0.1:{mgmt}", timeout=10.0)
        # IPv4 → gate. Clear default AAAA so Pebble does not dial [::1]:80.
        self._challtest_post(client, "/set-default-ipv4", {"ip": gate_ip})
        self._challtest_post(client, "/set-default-ipv6", {"ip": ""})

    @staticmethod
    def _challtest_post(client: HttpClient, path: str, body: dict) -> None:
        client.post(
            path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            expect_status=None,
        )

    def _directory_ok(self) -> bool:
        try:
            req = urllib.request.Request(self.directory_url)
            with urllib.request.urlopen(req, context=self._minica_ctx(), timeout=3) as resp:
                return int(resp.status) == 200
        except OSError:
            return False

    def _fetch_root(self) -> None:
        req = urllib.request.Request(f"{self._mgmt_base}/roots/0")
        with urllib.request.urlopen(req, context=self._minica_ctx(), timeout=10) as resp:
            self.root_ca.write_bytes(resp.read())

    def _extract_minica(self) -> None:
        if self.minica.is_file():
            return
        cid = self.docker.service_container_id(PEBBLE_SVC)
        self.docker.sh.run(
            ["docker", "cp", f"{cid}:/test/certs/pebble.minica.pem", str(self.minica)],
            check=True,
            capture=True,
        )

    def _published(self, service: str, port: int) -> int:
        result = self.docker.sh.compose(
            "port", service, str(port), capture=True, check=True
        )
        return int((result.stdout or "").strip().rsplit(":", 1)[-1])

    def _container_ip(self, service: str) -> str:
        cid = self.docker.service_container_id(service)
        result = self.docker.sh.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                cid,
            ],
            check=True,
            capture=True,
        )
        ip = (result.stdout or "").strip()
        assert ip, f"no IP for {service}"
        return ip

    def _minica_ctx(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=str(self.minica))

    @staticmethod
    def _config(http_port: int) -> dict:
        return {
            "pebble": {
                "listenAddress": "0.0.0.0:14000",
                "managementListenAddress": "0.0.0.0:15000",
                "certificate": "test/certs/localhost/cert.pem",
                "privateKey": "test/certs/localhost/key.pem",
                "httpPort": http_port,
                "tlsPort": 5001,
                "ocspResponderURL": "",
                "externalAccountBindingRequired": False,
            }
        }


def pebble_services() -> dict:
    """Compose services for Pebble + challtestsrv (same network as the gate)."""
    return {CHALLTEST_SVC: _challtest_svc(), PEBBLE_SVC: _pebble_svc()}


def _challtest_svc() -> dict:
    return {
        "image": CHALLTEST_IMAGE,
        # Empty default IPv6 so Pebble does not prefer ::1 over the gate A record.
        "command": [
            "-http01",
            "",
            "-https01",
            "",
            "-tlsalpn01",
            "",
            "-defaultIPv6",
            "",
        ],
        "ports": ["127.0.0.1::8055"],
    }


def _pebble_svc() -> dict:
    return {
        "image": PEBBLE_IMAGE,
        "command": [
            "-config",
            "/test/config/pebble-e2e.json",
            "-dnsserver",
            f"{CHALLTEST_SVC}:8053",
            "-strict=false",
        ],
        "environment": {"PEBBLE_VA_NOSLEEP": "1", "PEBBLE_WFE_NONCEREJECT": "0"},
        "volumes": ["./pebble-e2e.json:/test/config/pebble-e2e.json:ro"],
        "ports": ["127.0.0.1::14000", "127.0.0.1::15000"],
        "depends_on": [CHALLTEST_SVC],
    }
