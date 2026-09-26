"""App manifest loading, AppSpec, and stack render."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from raft.config.paths import find_package_root
from raft.config.settings_types import EdgeConfig, EdgeStream
from raft.models.app_document import AppDocument
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.readiness_spec import ReadinessSpec
from raft.models.registry import AppRegistry
from raft.models.stack import load_stack
from raft.services.render import StackRenderer

from ..base import RaftTestCase, write_applied_app, write_inventory


def _write_manifest(
    checkout: Path,
    *,
    name: str = "web",
    context: str | None = ".",
    www: bool = True,
    port: int = 80,
    dockerfile: str | None = None,
    extra_hosts=None,
    probe: str = "/",
    resources: bool = False,
    source: str = "local",
    public_host: str | None = None,
    repo: str | None = None,
    image: str | None = None,
    tls: str = "off",
    registry_root=None,
) -> None:
    path = checkout / ".raft" / "app.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "apiVersion: raft/v1",
        "kind: App",
        "metadata:",
        f"  name: {name}",
        "spec:",
        f"  publicHost: {public_host or f'{name}.test'}",
        f"  source: {source}",
        f"  path: apps/{name}",
        f"  tls: {tls}",
        f"  www: {'true' if www else 'false'}",
    ]
    if repo:
        lines.append(f"  repo: {repo}")
    if image:
        lines.append(f"  image: {image}")
    if extra_hosts is not None:
        if isinstance(extra_hosts, str):
            lines.append(f'  extraHosts: "{extra_hosts}"')
        else:
            lines.append("  extraHosts:")
            for h in extra_hosts:
                lines.append(f"    - {h}")
    lines.append("  ports:")
    lines.append("    - name: http")
    lines.append(f"      containerPort: {port}")
    lines.append("      expose: http")
    if context is not None:
        lines.append("  build:")
        lines.append(f"    context: {context}")
        if dockerfile:
            lines.append(f"    dockerfile: {dockerfile}")
    lines.append("  readiness:")
    lines.append("    type: http")
    lines.append("    port: http")
    lines.append(f"    path: {probe}")
    if resources:
        lines.extend(
            [
                "  resources:",
                "    limits:",
                '      cpu: "250m"',
                "      memory: 64Mi",
                "    requests:",
                '      cpu: "50m"',
                "      memory: 16Mi",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if registry_root is not None:
        reg = Path(registry_root) / "state" / "apps" / f"{name}.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


class TestAppSpec(RaftTestCase):
    def test_load_and_server_names(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_manifest(checkout, www=True, extra_hosts=["alias.test"])
        c = AppDocument.load_contract(checkout)
        assert c.ports[0].container_port == 80
        assert c.tls == "off"
        assert c.build_context == "."
        assert c.server_names("example.com") == (
            "example.com",
            "www.example.com",
            "alias.test",
        )

    def test_server_names_skips_duplicates(self) -> None:
        c = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            www=True,
            extra_hosts=("example.com", "www.example.com", "  ", "other.test"),
        )
        assert c.server_names("example.com") == (
            "example.com",
            "www.example.com",
            "other.test",
        )

    def test_resources_and_dockerfile(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_manifest(checkout, context="svc", dockerfile="Dockerfile.web", resources=True)
        c = AppDocument.load_contract(checkout)
        assert c.dockerfile == "Dockerfile.web"
        assert c.cpus_limit == "0.25"
        assert c.memory_limit == "64M"
        assert c.cpus_reservation == "0.05"
        assert c.memory_reservation == "16M"

    def test_rejects_kind_service_and_legacy_port(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: Service\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n  ports:\n"
            "    - name: http\n      containerPort: 80\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="kind must be"):
            AppDocument.load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n  port: 80\n"
            "  ports:\n    - name: http\n      containerPort: 80\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec.port is not supported"):
            AppDocument.load_contract(checkout)

    def test_rejects_readiness_probe_legacy(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n"
            "  readinessProbe:\n    httpGet:\n      path: /\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="readinessProbe is not supported"):
            AppDocument.load_contract(checkout)

    def test_rejects_service_yaml_only(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "service.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n",
            encoding="utf-8",
        )
        with pytest.raises(FileNotFoundError, match="missing App manifest"):
            AppDocument.load_contract(checkout)

    def test_stream_and_host_ports(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            """apiVersion: raft/v1
kind: App
metadata:
  name: mail
spec:
  publicHost: mail.example.com
  source: local
  tls: origin
  ports:
    - name: http
      containerPort: 80
      expose: http
    - name: smtp
      containerPort: 25
      expose: stream
      publicPort: 25
    - name: submission
      containerPort: 587
      expose: host
      publicPort: 587
  readiness:
    type: tcp
    port: smtp
  build:
    context: .
""",
            encoding="utf-8",
        )
        c = AppDocument.load_contract(checkout)
        assert c.tls == "origin"
        assert [p.expose for p in c.ports] == ["http", "stream", "host"]
        assert c.readiness.type == "tcp"
        assert c.readiness.port == "smtp"

    def test_registry_write_delete(self) -> None:
        doc = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "web"},
            "spec": {
                "publicHost": "web.test",
                "source": "local",
                "path": "apps/web",
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
                    "spec": {
                        **doc["spec"],
                        "publicHost": "web.test",
                        "path": "apps/other",
                    },
                },
            )
        assert AppRegistry(self.tmp_path).delete("web") is True
        assert AppRegistry(self.tmp_path).delete("missing") is False

    def test_parse_rejects_bad_yaml_and_api(self) -> None:
        path = self.tmp_path / "bad.yaml"
        path.write_text(":\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid YAML"):
            AppDocument.load(path)
        path.write_text("- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            AppDocument.load(path)
        with pytest.raises(ValueError, match="apiVersion"):
            AppDocument.parse(
                {"apiVersion": "x", "kind": "App", "metadata": {"name": "a"}},
                path=path,
            )

    def test_parse_rejects_bad_www_and_build_types(self) -> None:
        path = self.tmp_path / "app.yaml"
        base = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": {
                "source": "local",
                "publicHost": "a.test",
                "path": "apps/a",
                "ports": [{"name": "http", "containerPort": 80}],
            },
        }
        with pytest.raises(RuntimeError, match="spec.www must be a boolean"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "www": "yes"}},
                path=path,
            )
        with pytest.raises(RuntimeError, match="build.context must be a string"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "build": {"context": 1}}},
                path=path,
            )
        with pytest.raises(RuntimeError, match="build.dockerfile must be a string"):
            AppDocument.parse(
                {
                    **base,
                    "spec": {**base["spec"], "build": {"dockerfile": ["Dockerfile"]}},
                },
                path=path,
            )

    def test_load_app_file_oserror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        path = self.tmp_path / "app.yaml"
        path.write_text("x: 1\n", encoding="utf-8")
        monkeypatch.setattr(
            Path,
            "read_text",
            lambda self, *a, **k: (_ for _ in ()).throw(OSError("EACCES")),
        )
        with pytest.raises(RuntimeError, match="cannot read App manifest"):
            AppDocument.load(path)


class TestStackRenderer(RaftTestCase):
    def test_render_http_only_no_tls_snippets(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack).render()
        apps_yaml = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "wget" in apps_yaml
        assert 'expose:\n      - "80"' in apps_yaml
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"80:80"' in edge_yaml
        assert '"443:443"' in edge_yaml
        hosts = (self.tmp_path / "generated" / "nginx" / "router" / "hosts.conf").read_text(
            encoding="utf-8"
        )
        assert "upstream web_http" in hosts or "include /etc/nginx/upstreams/web-http.conf" in hosts
        assert "proxy_pass http://web_http" in hosts
        tls_dir = self.tmp_path / "generated" / "nginx" / "gate-tls"
        assert list(tls_dir.glob("*.conf")) == []
        upstream = self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf"
        assert upstream.is_file()

    def test_render_tls_origin_writes_snippet(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack).render()
        tls = (self.tmp_path / "generated" / "nginx" / "gate-tls" / "web.conf").read_text(
            encoding="utf-8"
        )
        assert "listen 443 ssl" in tls
        assert "certs/web/origin.pem" in tls

    def test_render_rejects_undeclared_stream_port(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
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
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with pytest.raises(RuntimeError, match="not declared in settings edge.streams"):
            StackRenderer(stack, edge=EdgeConfig(http=80, https=None, streams=())).render()

    def test_render_stream_and_host(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            extra={
                "ports": [
                    {"name": "http", "containerPort": 80, "expose": "http"},
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "stream",
                        "publicPort": 25,
                    },
                    {
                        "name": "submission",
                        "containerPort": 587,
                        "expose": "host",
                        "publicPort": 587,
                    },
                ],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        edge = EdgeConfig(
            http=80,
            https=443,
            streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),),
        )
        StackRenderer(stack, edge=edge).render()
        apps = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert '"587:587"' in apps
        assert "nc -z" in apps
        streams = (
            self.tmp_path / "generated" / "nginx" / "gate-stream" / "streams.conf"
        ).read_text(encoding="utf-8")
        assert "listen 25" in streams
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"25:25"' in edge_yaml

    def test_render_empty_apps(self) -> None:
        stack = load_stack(self.tmp_path)
        StackRenderer(stack).render()
        text = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "services: {}" in text

    def test_validate_requires_build_context(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            build_context=None,
            extra={"build": {}},
        )
        stack = load_stack(self.tmp_path)
        with pytest.raises(ValueError, match="context is required"):
            StackRenderer(stack).render()

    def test_render_volumes_env_depends_on(self) -> None:
        write_applied_app(
            self.tmp_path,
            "stack-redis",
            source="docker",
            image="redis",
            public_host="",
            build_context=None,
            extra={
                "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
                "readiness": {"type": "tcp", "port": "redis"},
                "group": "demo",
                "envFile": "/home/raft/.raft/demo.env",
                "env": {"FOO": "bar"},
                "volumes": [
                    {
                        "hostPath": "/mnt/raft-data/demo/redis",
                        "containerPath": "/data",
                        "readOnly": False,
                    }
                ],
            },
        )
        write_applied_app(
            self.tmp_path,
            "stack-front",
            source="docker",
            image="ghcr.io/example/nginx",
            public_host="",
            build_context=None,
            extra={
                "ports": [
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "host",
                        "publicPort": 25,
                    }
                ],
                "readiness": {"type": "tcp", "port": "smtp"},
                "group": "demo",
                "dependsOn": ["stack-redis"],
                "envFile": "/home/raft/.raft/demo.env",
            },
        )
        stack = load_stack(self.tmp_path)
        StackRenderer(stack).render()
        apps = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "env_file:" in apps
        assert "/home/raft/.raft/demo.env" in apps
        assert "FOO: bar" in apps
        assert "/mnt/raft-data/demo/redis:/data" in apps
        assert "demo-stack-redis:" in apps
        assert "condition: service_started" in apps
        assert '"25:25"' in apps


class TestAppSpecExtensions(RaftTestCase):
    def test_parse_group_volumes_env(self) -> None:
        data = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "stack-redis"},
            "spec": {
                "source": "docker",
                "image": "redis",
                "ref": "alpine",
                "path": "apps/stack-redis",
                "group": "demo",
                "dependsOn": ["stack-front"],
                "envFile": "/home/raft/.raft/demo.env",
                "env": {"A": "1"},
                "volumes": [
                    {
                        "name": "data",
                        "hostPath": "/mnt/raft-data/demo/redis",
                        "containerPath": "/data",
                        "readOnly": True,
                    }
                ],
                "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
                "readiness": {"type": "tcp", "port": "redis"},
            },
        }
        app, spec = AppDocument.parse(data, path=Path("app.yaml"))
        assert app.public_host == ""
        assert spec.group == "demo"
        assert spec.depends_on == ("stack-front",)
        assert spec.env_file == "/home/raft/.raft/demo.env"
        assert spec.env == (("A", "1"),)
        assert len(spec.volumes) == 1
        assert spec.volumes[0].read_only is True
        assert spec.none_ports()[0].name == "redis"

    def test_rejects_bad_group_and_volume_traversal(self) -> None:
        base = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "x"},
            "spec": {
                "source": "docker",
                "image": "redis",
                "path": "apps/x",
                "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
                "readiness": {"type": "none"},
            },
        }
        bad_group = yaml.safe_load(yaml.safe_dump(base))
        bad_group["spec"]["group"] = "Mailu"
        with pytest.raises(ValueError, match="spec.group"):
            AppDocument.parse(bad_group, path=Path("g.yaml"))
        bad_vol = yaml.safe_load(yaml.safe_dump(base))
        bad_vol["spec"]["volumes"] = [
            {"hostPath": "/tmp/../etc/passwd", "containerPath": "/data"}
        ]
        with pytest.raises(ValueError, match="must not contain"):
            AppDocument.parse(bad_vol, path=Path("v.yaml"))


class TestFindPackageRoot(RaftTestCase):
    def test_bundled(self) -> None:
        root = find_package_root()
        assert (root / "compose.yaml").is_file()
        assert (root / "nginx" / "gate" / "nginx.conf").is_file()
