"""Coverage for edge settings, ports, readiness, doctor drift, and render edges."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.adapters.docker import DockerStack
from raft.adapters.nginx import NginxUpstreams
from raft.config.settings import load_config
from raft.config.settings_types import EdgeConfig, EdgeStream
from raft.models.app import App
from raft.models.app_document import AppDocument
from raft.models.app_spec_fields import AppSpecFields
from raft.models.manifest import AppSpec
from raft.models.registry import AppRegistry
from raft.models.ports import PortSpec, parse_ports
from raft.models.readiness_parser import parse_readiness
from raft.models.readiness_spec import ReadinessSpec
from raft.models.stack import load_stack
from raft.services.cutover import CutoverSession
from raft.services.doctor import INFRA, Doctor
from raft.services.edge import StreamEdge
from raft.services.orchestrator import Orchestrator
from raft.services.readiness import ReadinessStrategy
from raft.services.render import StackRenderer

from ..base import RaftTestCase, make_app, make_stack, write_applied_app


def _doctor(stack, *, shell=None, docker=None, auth=None) -> Doctor:
    doctor = Doctor(stack)
    doctor.sh = shell if shell is not None else MagicMock()
    doctor.auth = auth if auth is not None else MagicMock()
    doctor.docker = docker if docker is not None else MagicMock()
    original_run = doctor.run

    def run_with_host_ok():
        with patch(
            "raft.services.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=True,
        ):
            return original_run()

    doctor.run = run_with_host_ok  # type: ignore[method-assign]
    return doctor


class TestSettingsEdgeErrors(RaftTestCase):
    def test_edge_validation_errors(self) -> None:
        cases = [
            ("edge: nope\n", "edge must be a mapping"),
            ("edge:\n  http: 99999\n", "out of range"),
            ("edge:\n  streams: {}\n", "must be a list"),
            ("edge:\n  streams:\n    - x\n", "must be an object"),
            ("edge:\n  streams:\n    - port: 25\n", "name is required"),
            (
                "edge:\n  streams:\n    - name: a\n      port: 25\n"
                "    - name: a\n      port: 26\n",
                "duplicate name",
            ),
            ("edge:\n  streams:\n    - name: a\n", "port is required"),
            (
                "edge:\n  streams:\n    - name: a\n      port: 0\n",
                "out of range",
            ),
            (
                "edge:\n  http: 25\n  streams:\n    - name: a\n      port: 25\n",
                "conflicts with edge.http",
            ),
            (
                "edge:\n  https: 25\n  streams:\n    - name: a\n      port: 25\n",
                "conflicts with edge.https",
            ),
            (
                "edge:\n  streams:\n    - name: a\n      port: 25\n" "      protocol: sctp\n",
                "protocol must be",
            ),
        ]
        for body, match in cases:
            (self.tmp_path / "settings.yaml").write_text(body, encoding="utf-8")
            with pytest.raises(RuntimeError, match=match):
                load_config(self.tmp_path)


class TestPortsAndReadinessCoverage(RaftTestCase):
    def test_port_validation_errors(self) -> None:
        path = Path("app.yaml")
        with pytest.raises(ValueError, match="expose must be"):
            PortSpec(name="x", container_port=80, expose="quic").validate(path=path)
        with pytest.raises(ValueError, match="protocol must be"):
            PortSpec(name="x", container_port=80, expose="http", protocol="sctp").validate(
                path=path
            )
        with pytest.raises(ValueError, match="containerPort out of range"):
            PortSpec(name="x", container_port=0, expose="http").validate(path=path)
        with pytest.raises(ValueError, match="publicPort out of range"):
            PortSpec(
                name="x",
                container_port=25,
                expose="stream",
                public_port=0,
            ).validate(path=path)
        with pytest.raises(ValueError, match="publicPort is only valid"):
            PortSpec(name="x", container_port=80, expose="http", public_port=80).validate(path=path)
        with pytest.raises(ValueError, match="spec.ports is required"):
            parse_ports({}, path)
        with pytest.raises(ValueError, match="non-empty list"):
            parse_ports({"ports": []}, path)
        with pytest.raises(ValueError, match="must be an object"):
            parse_ports({"ports": ["x"]}, path)
        with pytest.raises(ValueError, match="name is required"):
            parse_ports({"ports": [{"containerPort": 80}]}, path)
        with pytest.raises(ValueError, match="containerPort is required"):
            parse_ports({"ports": [{"name": "http"}]}, path)

    def test_readiness_paths(self) -> None:
        path = Path("app.yaml")
        ports = (
            PortSpec(name="http", container_port=80, expose="http"),
            PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
        )
        with pytest.raises(ValueError, match="must be an object"):
            parse_readiness({"readiness": "x"}, ports, path)
        with pytest.raises(ValueError, match="readiness.type must be"):
            parse_readiness({"readiness": {"type": "udp"}}, ports, path)
        with pytest.raises(ValueError, match="not in ports"):
            parse_readiness({"readiness": {"type": "tcp", "port": "missing"}}, ports, path)
        with pytest.raises(ValueError, match="requires an expose=http"):
            parse_readiness({"readiness": {"type": "http", "port": "smtp"}}, ports, path)
        r = parse_readiness({"readiness": {"type": "none"}}, ports, path)
        assert r.type == "none"
        assert r.timeout_seconds == 120.0
        assert r.start_period_seconds == 45.0
        r2 = parse_readiness({"readiness": {"type": "http", "path": "ready"}}, ports, path)
        assert r2.path == "/ready"
        r3 = parse_readiness({}, ports, path)
        assert r3.port == "http"
        r4 = parse_readiness(
            {},
            (PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),),
            path,
        )
        assert r4.type == "tcp"
        spec = ReadinessSpec(type="http", port=None, path="/")
        assert spec.resolve_port(ports).name == "http"
        with pytest.raises(KeyError):
            ReadinessSpec(type="tcp", port="nope").resolve_port(ports)
        assert ReadinessSpec(type="none").resolve_port(ports) is None
        assert ReadinessSpec(type="tcp").resolve_port(()) is None

    def test_readiness_timing_defaults_and_overrides(self) -> None:
        path = Path("app.yaml")
        ports = (PortSpec(name="http", container_port=80, expose="http"),)
        defaults = parse_readiness(
            {"readiness": {"type": "tcp", "port": "http"}},
            ports,
            path,
        )
        assert defaults.timeout_seconds == 120.0
        assert defaults.start_period_seconds == 45.0
        assert defaults.interval_seconds == 2.0
        assert defaults.retries == 15
        assert "timeoutSeconds=120s" in defaults.timing_summary()

        custom = parse_readiness(
            {
                "readiness": {
                    "type": "tcp",
                    "port": "http",
                    "timeoutSeconds": 180,
                    "startPeriodSeconds": 60,
                    "intervalSeconds": 3,
                    "probeTimeoutSeconds": 2,
                    "retries": 10,
                },
            },
            ports,
            path,
        )
        assert custom.timeout_seconds == 180.0
        assert custom.start_period_seconds == 60.0
        assert custom.interval_seconds == 3.0
        assert custom.retries == 10

        # Raising startPeriod without timeoutSeconds auto-bumps the wait budget.
        long_start = parse_readiness(
            {
                "readiness": {
                    "type": "tcp",
                    "port": "http",
                    "startPeriodSeconds": 90,
                },
            },
            ports,
            path,
        )
        assert long_start.timeout_seconds >= 90 + 15 * 2 + 15

        with pytest.raises(ValueError, match="greater than startPeriodSeconds"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "timeoutSeconds": 30,
                        "startPeriodSeconds": 45,
                    },
                },
                ports,
                path,
            )
        with pytest.raises(ValueError, match="at least startPeriodSeconds \\+ interval"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "timeoutSeconds": 46,
                        "startPeriodSeconds": 45,
                        "intervalSeconds": 2,
                    },
                },
                ports,
                path,
            )
        with pytest.raises(ValueError, match="must be > 0"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "retries": 0,
                    },
                },
                ports,
                path,
            )
        with pytest.raises(ValueError, match="timeoutSeconds must be a number"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "timeoutSeconds": "slow",
                    },
                },
                ports,
                path,
            )
        with pytest.raises(ValueError, match="startPeriodSeconds must be > 0"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "startPeriodSeconds": 0,
                    },
                },
                ports,
                path,
            )
        with pytest.raises(ValueError, match="retries must be an integer"):
            parse_readiness(
                {
                    "readiness": {
                        "type": "tcp",
                        "port": "http",
                        "retries": "many",
                    },
                },
                ports,
                path,
            )


class TestManifestCoverage(RaftTestCase):
    def test_more_parse_errors(self) -> None:
        path = Path("x.yaml")
        with pytest.raises(ValueError, match="metadata must be an object"):
            AppDocument.parse(
                {"apiVersion": "raft/v1", "kind": "App", "metadata": "nope"},
                path=path,
            )
        with pytest.raises(ValueError, match="metadata.name is required"):
            AppDocument.parse(
                {"apiVersion": "raft/v1", "kind": "App", "metadata": {}},
                path=path,
            )
        with pytest.raises(ValueError, match="spec must be an object"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": [],
                },
                path=path,
            )
        with pytest.raises(ValueError, match="YAML true is not valid"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "publicHost": "a.test",
                        "source": "local",
                        "tls": True,
                        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    },
                },
                path=path,
            )
        with pytest.raises(ValueError, match="tls=origin requires"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "source": "local",
                        "tls": "origin",
                        "ports": [
                            {
                                "name": "smtp",
                                "containerPort": 25,
                                "expose": "stream",
                                "publicPort": 25,
                            }
                        ],
                    },
                },
                path=path,
            )

    def test_resources_memory_helpers(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            """apiVersion: raft/v1
kind: App
metadata:
  name: web
spec:
  publicHost: web.test
  source: local
  ports:
    - name: http
      containerPort: 80
      expose: http
  resources:
    limits:
      cpu: null
      memory: null
    requests:
      cpu: ""
      memory: ""
""",
            encoding="utf-8",
        )
        c = AppDocument.load_contract(checkout)
        assert c.cpus_limit == "0.50"
        assert c.memory_limit == "128M"


class TestAdapterCoverage(RaftTestCase):
    def test_nginx_fallback_and_docker_ports(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("lonely"),))
        nginx = NginxUpstreams(stack, MagicMock())
        nginx.ensure_steady_file(stack.apps[0])
        path = stack.upstreams_dir / "lonely-http.conf"
        assert path.is_file()

        shell = MagicMock()
        docker = DockerStack(stack, shell)
        shell.compose.return_value = MagicMock(stdout="cid\n", returncode=0)
        shell.docker.return_value = MagicMock(stdout="", returncode=1)
        assert docker.gate_published_ports() == []
        shell.docker.return_value = MagicMock(stdout="80/tcp\n", returncode=0)
        assert docker.gate_published_ports() == [80]

    def test_readiness_wait_predicates(self) -> None:
        app = make_app()
        stack = make_stack(self.tmp_path, (app,))
        http = MagicMock()
        http.public_host_ok.return_value = True
        http.tcp_port_ok.return_value = True
        strategy = ReadinessStrategy(
            kind="http",
            port=PortSpec(name="http", container_port=80, expose="http"),
        )
        assert strategy.wait_predicate(app, stack, http)() is True
        tcp = ReadinessStrategy(
            kind="tcp",
            port=PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
        )
        assert tcp.wait_predicate(app, stack, http)() is True
        assert tcp.wait_predicate(app, stack, http, tcp_ok=lambda p: p == 25)() is True
        internal = ReadinessStrategy(
            kind="tcp",
            port=PortSpec(name="http", container_port=8000, expose="none"),
        )
        assert internal.wait_predicate(app, stack, http)() is False
        assert (
            internal.wait_predicate(
                app, stack, http, compose_ready=lambda: True
            )()
            is True
        )
        assert (
            internal.wait_predicate(
                app, stack, http, tcp_ok=lambda p: p == 8000
            )()
            is True
        )
        with pytest.raises(ValueError):
            ReadinessStrategy(
                kind="weird",
                port=PortSpec(name="http", container_port=80, expose="http"),
            ).healthcheck_test()
        with pytest.raises(ValueError):
            ReadinessStrategy(
                kind="weird",
                port=PortSpec(name="http", container_port=80, expose="http"),
            ).wait_predicate(app, stack, http)


class TestRenderDoctorOrchCoverage(RaftTestCase):
    def test_stream_protocol_mismatch_and_empty_edge(self) -> None:
        app = make_app("mail", public_host="mail.example.com")
        port = PortSpec(
            name="smtp",
            container_port=25,
            expose="stream",
            public_port=25,
            protocol="udp",
        )
        spec = AppSpec(ports=(port,))
        edge = EdgeConfig(streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),))
        with pytest.raises(RuntimeError, match="does not match"):
            StreamEdge().contribute(app, spec, port, edge=edge)

        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=None, https=None, streams=())).render()
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert "ports:\n      []" in edge_yaml

    def test_render_dockerfile_and_stale_prune(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            extra={"build": {"context": ".", "dockerfile": "Dockerfile.web"}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        tls_dir = stack.generated_dir() / "nginx" / "gate-tls"
        tls_dir.mkdir(parents=True, exist_ok=True)
        (tls_dir / "stale.conf").write_text("x", encoding="utf-8")
        http_dir = stack.generated_dir() / "nginx" / "gate-http"
        http_dir.mkdir(parents=True, exist_ok=True)
        (http_dir / "old.conf").write_text("x", encoding="utf-8")
        up = stack.upstreams_dir
        up.mkdir(parents=True, exist_ok=True)
        (up / "old.conf").write_text("x", encoding="utf-8")
        StackRenderer(stack).render()
        assert not (tls_dir / "stale.conf").exists()
        assert not (http_dir / "old.conf").exists()
        assert not (up / "old.conf").exists()
        apps = (stack.generated_dir() / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "dockerfile: Dockerfile.web" in apps

    def test_doctor_gate_drift_and_udp_listener(self) -> None:
        write_applied_app(self.tmp_path, "app")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: null\n  streams:\n"
            "    - name: dns\n      port: 53\n      protocol: udp\n",
            encoding="utf-8",
        )
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller", "app"]
        docker.gate_published_ports.return_value = [80, 999]
        with patch("raft.services.doctor.shutil.which", return_value="/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = {
                    (r.service, r.check): r
                    for r in _doctor(stack, shell=shell, docker=docker).run()
                }
        assert results[("raft-gate", "ports")].status == "fail"
        assert "raft gate recreate" in results[("raft-gate", "ports")].fix
        assert results[(INFRA, "port 53/udp")].status == "ok"

    def test_doctor_no_edge_and_gate_up_not_listening(self) -> None:
        write_applied_app(self.tmp_path, "app")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: null\n  https: null\n  streams: []\n",
            encoding="utf-8",
        )
        stack = load_stack(self.tmp_path)
        docker = MagicMock()
        docker.running_services.return_value = []
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with patch("raft.services.doctor.shutil.which", return_value="/bin/docker"):
            results = {
                (r.service, r.check): r
                for r in _doctor(stack, shell=shell, docker=docker).run()
            }
        assert results[(INFRA, "edge")].status == "warn"

        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: null\n", encoding="utf-8"
        )
        docker.running_services.return_value = ["raft-gate"]
        docker.gate_published_ports.return_value = []
        with patch("raft.services.doctor.shutil.which", return_value="/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = {
                    (r.service, r.check): r
                    for r in _doctor(stack, shell=shell, docker=docker).run()
                }
        assert results[(INFRA, "port 80")].status == "warn"
        assert results[("raft-gate", "ports")].status == "warn"

    def test_orchestrator_none_readiness(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "none"}},
        )
        stack = load_stack(self.tmp_path)
        orch = Orchestrator(stack)
        orch.docker = MagicMock()
        orch.nginx = MagicMock()
        orch.http = MagicMock()
        orch.syncer = MagicMock()
        orch.docker.running_services.side_effect = [
            [],
            ["raft-gate", "raft-router", "raft-controller", "app"],
        ]
        with patch.object(orch, "sync"):
            orch.start()
        orch.http.public_host_ok.assert_not_called()

    def test_doctor_stream_only_upstream_and_tls_ok(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            tls="origin",
            extra={
                "ports": [
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "stream",
                        "publicPort": 25,
                    }
                ],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )
        d = self.tmp_path / "certs" / "mail"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("p", encoding="utf-8")
        (d / "origin.key").write_text("k", encoding="utf-8")
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: 443\n  streams:\n" "    - name: smtp\n      port: 25\n",
            encoding="utf-8",
        )
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.gate_published_ports.return_value = [80, 443, 25]
        with patch("raft.services.doctor.shutil.which", return_value="/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = {
                    (r.service, r.check): r
                    for r in _doctor(stack, shell=shell, docker=docker).run()
                }
        assert results[("mail", "upstream")].detail.startswith("n/a")
        assert results[("mail", "certs")].status == "ok"

    def test_render_aliases_and_errors(self) -> None:
        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        renderer = StackRenderer(stack)
        specs = renderer.load_all_contracts()
        assert "web" in specs
        with pytest.raises(RuntimeError, match="missing AppSpec"):
            renderer.render(specs={})
        write_applied_app(
            self.tmp_path,
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            build_context=None,
        )
        stack2 = load_stack(self.tmp_path)
        StackRenderer(stack2).render()
        text = (stack2.generated_dir() / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "image: ghcr.io/org/hub:main" in text

    def test_render_build_outside_home(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            path="apps/web",
            extra={"build": {"context": "/tmp/outside-raft-build"}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with pytest.raises(ValueError, match="outside raft data home"):
            StackRenderer(stack).render()

    def test_readiness_empty_port_name_and_defaults(self) -> None:
        path = Path("app.yaml")
        ports = (PortSpec(name="http", container_port=80, expose="http"),)
        r = parse_readiness(
            {"readiness": {"type": "http", "port": "  ", "path": ""}},
            ports,
            path,
        )
        assert r.port == "http"
        with pytest.raises(ValueError, match="requires a named port"):
            parse_readiness(
                {"readiness": {"type": "tcp"}},
                (),
                path,
            )
        spec = ReadinessSpec(type="tcp", port=None)
        assert spec.resolve_port(ports).name == "http"

    def test_manifest_extra_resource_branches(self) -> None:
        path = Path("x.yaml")
        base = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": {
                "publicHost": "a.test",
                "source": "local",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }
        with pytest.raises(ValueError, match="resources must be an object"):
            AppDocument.parse({**base, "spec": {**base["spec"], "resources": []}}, path=path)
        with pytest.raises(ValueError, match="limits/requests"):
            AppDocument.parse(
                {
                    **base,
                    "spec": {
                        **base["spec"],
                        "resources": {"limits": [], "requests": {}},
                    },
                },
                path=path,
            )
        with pytest.raises(ValueError, match="extraHosts"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "extraHosts": {"a": 1}}},
                path=path,
            )
        with pytest.raises(ValueError, match="spec.build"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "build": []}},
                path=path,
            )
        app, spec = AppDocument.parse(
            {
                **base,
                "spec": {
                    **base["spec"],
                    "tls": False,
                    "build": {"context": "  ", "dockerfile": "  "},
                    "extraHosts": "alias.test",
                    "www": False,
                },
            },
            path=path,
        )
        assert spec.tls == "off"
        assert spec.build_context is None
        assert spec.dockerfile is None
        assert spec.extra_hosts == ("alias.test",)
        with pytest.raises(ValueError, match="filename stem"):
            dest = self.tmp_path / "state" / "apps" / "wrong.yaml"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: a\nspec:\n"
                "  publicHost: a.test\n  source: local\n"
                "  ports:\n    - name: http\n      containerPort: 80\n"
                "      expose: http\n",
                encoding="utf-8",
            )
            load_stack(self.tmp_path)

    def test_stream_dir_stale_prune(self) -> None:
        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        stream_dir = stack.generated_dir() / "nginx" / "gate-stream"
        stream_dir.mkdir(parents=True, exist_ok=True)
        (stream_dir / "stale.conf").write_text("x", encoding="utf-8")
        StackRenderer(stack).render()
        assert not (stream_dir / "stale.conf").exists()

    def test_readiness_http_fallback_and_docker_non_digit(self) -> None:
        ports = (
            PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
            PortSpec(name="http", container_port=80, expose="http"),
        )
        assert ReadinessSpec(type="http", port=None).resolve_port(ports).name == "http"
        only_stream = (PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),)
        assert ReadinessSpec(type="http", port=None).resolve_port(only_stream).name == "smtp"

        shell = MagicMock()
        docker = DockerStack(make_stack(self.tmp_path), shell)
        shell.compose.return_value = MagicMock(stdout="cid\n", returncode=0)
        shell.docker.return_value = MagicMock(stdout="80/tcp weird\n", returncode=0)
        assert docker.gate_published_ports() == [80]
        app = make_app()
        stack = make_stack(self.tmp_path, (app,))
        http = MagicMock()
        http.tcp_port_ok.return_value = True
        strategy = ReadinessStrategy(
            kind="tcp",
            port=PortSpec(name="http", container_port=8080, expose="http"),
        )
        assert strategy.wait_predicate(app, stack, http)() is True
        http.tcp_port_ok.assert_called_with(8080)

    def test_server_names_blank_extra(self) -> None:
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            www=False,
            extra_hosts=("  ",),
        )
        assert spec.server_names("a.test") == ("a.test",)
        assert spec.http_ports()[0].name == "http"
        assert spec.stream_ports() == ()
        assert spec.host_ports() == ()

    def test_parse_memory_gi_and_cpu_millis(self) -> None:
        assert AppSpecFields._parse_memory("2Gi", default="1M") == "2G"
        assert AppSpecFields._parse_memory(None, default="1M") == "1M"
        assert AppSpecFields._parse_memory("  ", default="1M") == "1M"
        assert AppSpecFields._parse_cpu(None, default="0.1") == "0.1"
        assert AppSpecFields._parse_cpu("  ", default="0.1") == "0.1"
        assert AppSpecFields._parse_cpu("500m", default="0.1") == "0.5"

    def test_remaining_coverage_bits(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("edge:\n  streams: null\n", encoding="utf-8")
        assert load_config(self.tmp_path).edge.streams == ()

        path = Path("x.yaml")
        with pytest.raises(ValueError, match="does not match expected"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "publicHost": "a.test",
                        "source": "local",
                        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    },
                },
                path=path,
                expect_name="other",
            )
        with pytest.raises(ValueError, match="spec.source must be"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "publicHost": "a.test",
                        "source": "ftp",
                        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    },
                },
                path=path,
            )
        app, _ = AppDocument.parse(
            {
                "apiVersion": "raft/v1",
                "kind": "App",
                "metadata": {"name": "hub"},
                "spec": {
                    "publicHost": "hub.test",
                    "source": "docker",
                    "image": "ghcr.io/org/hub",
                    "repo": "git@github.com:org/hub.git",
                    "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                },
            },
            path=path,
        )
        assert app.repo == "git@github.com:org/hub.git"

        write_applied_app(
            self.tmp_path,
            "web",
            source="docker",
            image="ghcr.io/org/web",
            build_context=None,
            extra={"build": {"context": "."}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with patch("raft.services.render.logger") as log:
            StackRenderer(stack).render()
            assert log.debug.called

        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            extra={
                "ports": [
                    {"name": "http", "containerPort": 80, "expose": "http"},
                    {
                        "name": "sub",
                        "containerPort": 587,
                        "expose": "host",
                        "publicPort": 587,
                        "protocol": "udp",
                    },
                ],
                "readiness": {"type": "none"},
            },
        )
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(
            stack,
            edge=EdgeConfig(
                http=80,
                https=443,
                streams=(EdgeStream(name="dns", port=53, protocol="udp"),),
            ),
        ).render()
        apps = (stack.generated_dir() / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "587:587/udp" in apps
        edge_yaml = (stack.generated_dir() / "compose.edge.yaml").read_text(encoding="utf-8")
        assert "53:53/udp" in edge_yaml
        mail_block = apps.split("  mail:\n", 1)[1]
        assert "healthcheck:" not in mail_block.split("    restart:", 1)[0]

        app = App(
            name="hub",
            public_host="hub.test",
            source="docker",
            path="apps/hub",
            image="ghcr.io/org/hub",
            ref="main",
        )
        assert app.image_ref("sha256:abc") == "ghcr.io/org/hub@sha256:abc"

        assert AppSpecFields._parse_cpu(2.5, default="0.1") == "2.5"
        assert AppSpecFields._parse_cpu("0.75", default="0.1") == "0.75"
        assert AppSpecFields._parse_memory("10Mi", default="1M") == "10M"
        assert AppSpecFields._parse_memory("128M", default="1M") == "128M"

        with pytest.raises(ValueError, match="spec.ports is required"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "bare"},
                    "spec": None,
                },
                path=Path("bare.yaml"),
            )
        with pytest.raises(ValueError, match="spec.tls must be"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "publicHost": "a.test",
                        "source": "local",
                        "tls": "bogus",
                        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    },
                },
                path=Path("x.yaml"),
            )
        _app2, spec2 = AppDocument.parse(
            {
                "apiVersion": "raft/v1",
                "kind": "App",
                "metadata": {"name": "a"},
                "spec": {
                    "publicHost": "a.test",
                    "source": "local",
                    "extraHosts": "",
                    "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    "build": {"context": "."},
                },
            },
            path=Path("x.yaml"),
        )
        assert spec2.extra_hosts == ()

        doc = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "uniq"},
            "spec": {
                "publicHost": "shared.test",
                "source": "local",
                "path": "apps/uniq",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                "build": {"context": "."},
            },
        }
        AppRegistry(self.tmp_path).write(doc)
        with pytest.raises(ValueError, match="already used"):
            AppRegistry(self.tmp_path).write(
                {
                    **doc,
                    "metadata": {"name": "other"},
                    "spec": {**doc["spec"], "path": "apps/other"},
                }
            )
        other = self.tmp_path / "state" / "apps" / "clash.yaml"
        other.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: clash\nspec:\n"
            "  publicHost: shared.test\n  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n"
            "      expose: http\n  build:\n    context: .\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="publicHost values must be unique"):
            load_stack(self.tmp_path)

    def test_gate_listener_https_only(self) -> None:
        write_applied_app(self.tmp_path, "web", tls="origin")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=None, https=443, streams=())).render()
        listeners = (stack.generated_dir() / "nginx" / "gate-http" / "listeners.conf").read_text(
            encoding="utf-8"
        )
        assert "listen 443 ssl" in listeners
        assert "listen 80" not in listeners

    def test_shift_skips_wait_when_none(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "none"}},
        )
        stack = make_stack(
            self.tmp_path,
            (make_app(),),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        session = CutoverSession(
            stack=stack,
            app=stack.apps[0],
            docker=MagicMock(),
            nginx=MagicMock(),
            http=MagicMock(),
        )
        session.previous_image = "img:old"
        session.start_tmp_from_previous()
        session.docker.router_can_fetch.assert_not_called()
        with patch("raft.services.cutover.time.sleep"):
            session.shift_traffic_to_tmp()
            session.rebuild_stable_service()
