"""Kubernetes-shaped App contract loading and stack render."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ..base import RaftTestCase, write_inventory
from raft.models.contract import (
    ServiceContract,
    delete_registry_app,
    load_app_file,
    load_contract,
    parse_app_document,
    write_registry_app,
)
from raft.models.inventory import find_package_root, load_inventory, load_stack
from raft.services.render import StackRenderer

def _write_contract(
    checkout,
    *,
    name: str = "web",
    context: str | None = ".",
    www: bool = True,
    port: int = 80,
    dockerfile: str | None = None,
    extra_hosts=None,
    probe: str = "/",
    resources: bool = False,
    kind: str = "App",
    source: str = "local",
    public_host: str | None = None,
    repo: str | None = None,
    image: str | None = None,
    registry_root=None,
) -> None:
    path = checkout / ".raft" / "app.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "apiVersion: raft/v1",
        f"kind: {kind}",
        "metadata:",
        f"  name: {name}",
        "spec:",
        f"  publicHost: {public_host or f'{name}.test'}",
        f"  source: {source}",
        f"  path: apps/{name}",
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
    if context is not None:
        lines.append("  build:")
        lines.append(f"    context: {context}")
        if dockerfile:
            lines.append(f"    dockerfile: {dockerfile}")
    lines.append("  readinessProbe:")
    lines.append("    httpGet:")
    lines.append(f"      path: {probe}")
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

class TestServiceContract(RaftTestCase):
    def test_load_and_server_names(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_contract(checkout, www=True, extra_hosts=["alias.test"])
        c = load_contract(checkout)
        assert c.port == 80
        assert c.build_context == "."
        assert c.server_names("example.com") == (
            "example.com",
            "www.example.com",
            "alias.test",
        )

    def test_server_names_skips_duplicates(self) -> None:
        c = ServiceContract(
            www=True,
            extra_hosts=("example.com", "www.example.com", "  ", "other.test"),
        )
        assert c.server_names("example.com") == (
            "example.com",
            "www.example.com",
            "other.test",
        )

    def test_extra_hosts_string_and_www_false(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_contract(checkout, www=False, extra_hosts="only.test", context=None)
        c = load_contract(checkout)
        assert c.build_context is None
        assert c.server_names("hub.test") == ("hub.test", "only.test")

    def test_resources_cpu_millis_and_dockerfile(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_contract(
            checkout, context="svc", dockerfile="Dockerfile.web", resources=True
        )
        c = load_contract(checkout)
        assert c.dockerfile == "Dockerfile.web"
        assert c.cpus_limit == "0.25"
        assert c.memory_limit == "64M"
        assert c.cpus_reservation == "0.05"
        assert c.memory_reservation == "16M"

    def test_resource_numeric_cpu_and_gi_memory(self) -> None:
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
  resources:
    limits:
      cpu: 1
      memory: 1Gi
    requests:
      cpu: 0.5
      memory: ""
""",
            encoding="utf-8",
        )
        c = load_contract(checkout)
        assert c.cpus_limit == "1"
        assert c.memory_limit == "1G"
        assert c.cpus_reservation == "0.5"
        assert c.memory_reservation == "32M"

    def test_resource_empty_cpu_string_uses_default(self) -> None:
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
  resources:
    limits:
      cpu: "  "
      memory: 256M
""",
            encoding="utf-8",
        )
        c = load_contract(checkout)
        assert c.cpus_limit == "0.50"
        assert c.memory_limit == "256M"

    def test_resource_plain_cpu_string(self) -> None:
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
  resources:
    limits:
      cpu: "0.75"
      memory: 128M
""",
            encoding="utf-8",
        )
        assert load_contract(checkout).cpus_limit == "0.75"

    def test_kind_service_alias_and_metadata_mismatch(self) -> None:
        checkout = self.tmp_path / "app"
        checkout.mkdir()
        _write_contract(checkout, name="web", kind="Service")
        assert load_contract(checkout).metadata_name == "web"
        with pytest.raises(ValueError, match="metadata.name"):
            load_contract(checkout, expect_name="other")

    def test_rejects_bad_api_version(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: nope\nkind: App\nspec: {}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="apiVersion"):
            load_contract(checkout)

    def test_rejects_bad_kind_and_port(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: Pod\nspec: {}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="kind"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  ports:\n    - containerPort: 0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="containerPort|out of range"):
            load_contract(checkout)

    def test_rejects_bad_structures(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec: nope\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec must be an object"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  extraHosts: {x: 1}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="extraHosts"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  build: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec.build"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  readinessProbe: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="readinessProbe"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  resources: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="resources must be an object"):
            load_contract(checkout)

    def test_empty_optionals_and_service_yaml_fallback(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "service.yaml").write_text(
            """apiVersion: raft/v1
kind: App
metadata:
  name: web
spec:
  publicHost: web.test
  source: local
  www: false
  extraHosts: ""
  build:
    context: ""
    dockerfile: ""
  readinessProbe:
    httpGet:
      path: ""
""",
            encoding="utf-8",
        )
        c = load_contract(checkout)
        assert c.metadata_name == "web"
        assert c.build_context is None
        assert c.dockerfile is None
        assert c.probe_path == "/"
        assert c.extra_hosts == ()

    def test_registry_write_delete_and_stem_mismatch(self) -> None:
        doc = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "web"},
            "spec": {
                "publicHost": "web.test",
                "source": "local",
                "path": "apps/web",
                "build": {"context": "."},
            },
        }
        write_registry_app(self.tmp_path, doc)
        with pytest.raises(ValueError, match="already used"):
            write_registry_app(
                self.tmp_path,
                {
                    **doc,
                    "metadata": {"name": "other"},
                    "spec": {**doc["spec"], "publicHost": "web.test", "path": "apps/other"},
                },
            )
        bad = self.tmp_path / "state" / "apps" / "wrong.yaml"
        bad.write_text(
            yaml.safe_dump(
                {
                    **doc,
                    "metadata": {"name": "web"},
                }
            ),
            encoding="utf-8",
        )
        (self.tmp_path / "state" / "apps" / "web.yaml").unlink()
        with pytest.raises(ValueError, match="filename stem"):
            load_inventory(self.tmp_path)
        assert delete_registry_app(self.tmp_path, "missing") is False

    def test_extra_hosts_probe_resources_type_errors(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n  extraHosts: {a: 1}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="extraHosts"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n  readinessProbe: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="readinessProbe"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n"
            "  publicHost: web.test\n  source: local\n  resources:\n"
            "    limits: bad\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="limits/requests"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="publicHost"):
            load_contract(checkout)

    def test_legacy_flat_port_and_omitted_spec(self) -> None:
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
  port: 8080
""",
            encoding="utf-8",
        )
        assert load_contract(checkout).port == 8080
        (checkout / ".raft" / "app.yaml").write_text(
            """apiVersion: raft/v1
kind: App
metadata:
  name: web
spec:
  publicHost: web.test
  source: local
""",
            encoding="utf-8",
        )
        c = load_contract(checkout)
        assert c.port == 80
        assert c.www is True

    def test_invalid_yaml_and_missing(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text(":\n  -", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid YAML"):
            load_contract(checkout)
        with pytest.raises(FileNotFoundError, match="missing service contract"):
            load_contract(self.tmp_path / "missing")

    def test_rejects_non_mapping_document_and_bad_ports(self) -> None:
        checkout = self.tmp_path / "app"
        (checkout / ".raft").mkdir(parents=True)
        (checkout / ".raft" / "app.yaml").write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata: x\nspec:\n  publicHost: web.test\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="metadata"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  ports: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="ports"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  ports:\n    - 80\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="ports"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  readinessProbe:\n    httpGet: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="httpGet"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  resources:\n    limits: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="limits/requests"):
            load_contract(checkout)
        (checkout / ".raft" / "app.yaml").write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\nspec:\n  publicHost: web.test\n  source: local\n  port: 0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec.port"):
            load_contract(checkout)

class TestRender(RaftTestCase):
    def test_render_compose_and_nginx(self) -> None:
        checkout = self.tmp_path / "apps" / "web"
        checkout.mkdir(parents=True)
        _write_contract(
            checkout,
            context=".",
            dockerfile="Dockerfile",
            registry_root=self.tmp_path,
        )
        stack = load_stack(self.tmp_path)
        StackRenderer(stack).render()
        compose = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(
            encoding="utf-8"
        )
        assert "web:" in compose
        assert "build: ./apps/web" in compose or "context: ./apps/web" in compose
        assert "dockerfile: Dockerfile" in compose
        hosts = (
            self.tmp_path / "generated" / "nginx" / "router" / "hosts.conf"
        ).read_text(encoding="utf-8")
        assert "server_name web.test www.web.test" in hosts

    def test_render_docker_and_stale_tls_cleanup(self) -> None:
        checkout = self.tmp_path / "apps" / "hub"
        checkout.mkdir(parents=True)
        _write_contract(
            checkout,
            name="hub",
            www=False,
            context=None,
            source="docker",
            image="ghcr.io/org/hub",
            repo="git@github.com:org/hub.git",
            public_host="hub.test",
            registry_root=self.tmp_path,
        )
        stack = load_stack(self.tmp_path)
        tls_dir = self.tmp_path / "generated" / "nginx" / "gate-tls"
        tls_dir.mkdir(parents=True, exist_ok=True)
        (tls_dir / "old.conf").write_text("stale\n", encoding="utf-8")
        StackRenderer(stack).render()
        compose = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(
            encoding="utf-8"
        )
        assert "image: ghcr.io/org/hub:main" in compose
        assert not (tls_dir / "old.conf").exists()

    def test_render_requires_build_context_for_git(self) -> None:
        checkout = self.tmp_path / "apps" / "web"
        checkout.mkdir(parents=True)
        _write_contract(
            checkout,
            context=None,
            source="git",
            repo="git@github.com:org/web.git",
            registry_root=self.tmp_path,
        )
        stack = load_stack(self.tmp_path)
        with pytest.raises(ValueError, match="build"):
            StackRenderer(stack).render()

    def test_render_docker_ignores_build_and_rejects_outside_context(self) -> None:
        checkout = self.tmp_path / "apps" / "hub"
        checkout.mkdir(parents=True)
        _write_contract(
            checkout,
            name="hub",
            context=".",
            www=False,
            source="docker",
            image="ghcr.io/org/hub",
            public_host="hub.test",
            registry_root=self.tmp_path,
        )
        StackRenderer(load_stack(self.tmp_path)).render()

        hub_reg = self.tmp_path / "state" / "apps" / "hub.yaml"
        hub_reg.unlink(missing_ok=True)
        web = self.tmp_path / "apps" / "web"
        web.mkdir(parents=True, exist_ok=True)
        _write_contract(
            web, context="../../../etc", registry_root=self.tmp_path
        )
        with pytest.raises(ValueError, match="outside raft data home"):
            StackRenderer(load_stack(self.tmp_path)).render()

    def test_render_simple_build_path_and_missing_contract_map(self) -> None:
        checkout = self.tmp_path / "apps" / "web"
        checkout.mkdir(parents=True, exist_ok=True)
        _write_contract(checkout, context=".", registry_root=self.tmp_path)
        stack = load_stack(self.tmp_path)
        renderer = StackRenderer(stack)
        with pytest.raises(KeyError, match="missing contract"):
            renderer.render(contracts={})
        renderer.render()
        assert "build: ./apps/web" in renderer.compose_apps_path().read_text(
            encoding="utf-8"
        )

class TestInventoryHosts(RaftTestCase):
    def test_rejects_duplicate_hosts(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  a:
    public_host: same.test
    source: local
    path: apps/a
  b:
    public_host: same.test
    source: local
    path: apps/b
""",
        )
        with pytest.raises(ValueError, match="unique"):
            load_inventory(self.tmp_path)

    def test_docker_may_include_repo(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  hub:
    public_host: hub.test
    source: docker
    image: ghcr.io/org/hub
    ref: main
    repo: "git@github.com:org/hub.git"
    path: apps/hub
""",
        )
        apps = load_inventory(self.tmp_path)
        assert apps[0].repo == "git@github.com:org/hub.git"

    def test_contract_for_helper(self) -> None:
        write_inventory(
            self.tmp_path,
            """
services:
  web:
    public_host: web.test
    source: local
    path: apps/web
""",
        )
        checkout = self.tmp_path / "apps" / "web"
        checkout.mkdir(parents=True)
        _write_contract(checkout, name="web")
        stack = load_stack(self.tmp_path)
        assert isinstance(stack.contract_for(stack.apps[0]), ServiceContract)
        assert stack.generated_dir() == self.tmp_path / "generated"

    def test_find_package_root_bundled(self) -> None:
        orphan = Path(tempfile.mkdtemp(prefix="raft-orphan-"))
        try:
            found = find_package_root(start=orphan)
            assert (found / "compose.yaml").is_file()
            assert (found / "nginx").is_dir()
        finally:
            os.rmdir(orphan)

    def test_expect_name_and_null_spec(self) -> None:
        path = self.tmp_path / "state" / "apps" / "web.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: web\n"
            "spec:\n  publicHost: web.test\n  source: local\n  path: apps/web\n"
            "  build:\n    context: .\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="does not match"):
            load_app_file(path, expect_name="other")
        with pytest.raises(ValueError, match="metadata.name is required"):
            parse_app_document(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": ""},
                    "spec": {"publicHost": "x.test", "source": "local"},
                },
                path=path,
            )
        with pytest.raises(ValueError, match="publicHost"):
            parse_app_document(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "nully"},
                    "spec": None,
                },
                path=path,
            )
