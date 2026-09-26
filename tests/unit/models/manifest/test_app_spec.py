"""AppSpec parse and load coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.models.app_document import AppDocument
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.registry import AppRegistry

from .base import ManifestTestCase

MAIL_PORTS_YAML = """\
apiVersion: raft/v1
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
"""

REGISTRY_DOC = {
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


class TestAppSpec(ManifestTestCase):
    def test_load_and_server_names(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        self.write_manifest(checkout, www=True, extra_hosts=["alias.test"])
        c = AppDocument.load_contract(checkout)
        assert c.ports[0].container_port == 80 and c.tls == "off"
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
        self.write_manifest(checkout, context="svc", dockerfile="Dockerfile.web", resources=True)
        c = AppDocument.load_contract(checkout)
        assert c.dockerfile == "Dockerfile.web"
        assert c.cpus_limit == "0.25" and c.memory_limit == "64M"
        assert c.cpus_reservation == "0.05" and c.memory_reservation == "16M"

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
        (checkout / ".raft" / "app.yaml").write_text(MAIL_PORTS_YAML, encoding="utf-8")
        c = AppDocument.load_contract(checkout)
        assert c.tls == "origin"
        assert [p.expose for p in c.ports] == ["http", "stream", "host"]
        assert c.readiness.type == "tcp" and c.readiness.port == "smtp"

    def test_registry_write_delete(self) -> None:
        AppRegistry(self.tmp_path).write(REGISTRY_DOC)
        with pytest.raises(ValueError, match="already used"):
            AppRegistry(self.tmp_path).write(
                {
                    **REGISTRY_DOC,
                    "metadata": {"name": "other"},
                    "spec": {
                        **REGISTRY_DOC["spec"],
                        "publicHost": "web.test",
                        "path": "apps/other",
                    },
                }
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
                {"apiVersion": "x", "kind": "App", "metadata": {"name": "a"}}, path=path
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
            AppDocument.parse({**base, "spec": {**base["spec"], "www": "yes"}}, path=path)
        with pytest.raises(RuntimeError, match="build.context must be a string"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "build": {"context": 1}}}, path=path
            )
        with pytest.raises(RuntimeError, match="build.dockerfile must be a string"):
            AppDocument.parse(
                {**base, "spec": {**base["spec"], "build": {"dockerfile": ["Dockerfile"]}}},
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
