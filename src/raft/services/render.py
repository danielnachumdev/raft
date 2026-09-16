"""Render Compose + nginx fragments from applied App manifests + edge settings."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from ..config.paths import GENERATED_DIRNAME
from ..config.settings import EdgeConfig, load_config
from ..models.app import App
from ..models.manifest import AppSpec, load_app_file, registry_path
from ..models.stack import Stack
from .edge import EDGE_HANDLERS, EdgeFragments, TlsEdge
from .readiness import ReadinessStrategy

logger = logging.getLogger(__name__)

_GATE_NGINX_SUBDIRS = ("gate-tls", "gate-http", "gate-stream")
GATE_NGINX_RELOAD_STAMP = Path("state") / "gate-nginx.fingerprint"


def fingerprint_gate_nginx(stack_root: Path) -> str:
    """Stable hash of generated gate nginx fragments (tls / http / stream).

    Missing directories count as empty. Does not include ``compose.edge.yaml``
    (published-port changes still require ``raft gate recreate``).
    """
    base = stack_root / GENERATED_DIRNAME / "nginx"
    entries: list[tuple[str, bytes]] = []
    for sub in _GATE_NGINX_SUBDIRS:
        directory = base / sub
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                rel = f"{sub}/{path.relative_to(directory).as_posix()}"
                entries.append((rel, path.read_bytes()))
    digest = hashlib.sha256()
    for rel, data in sorted(entries, key=lambda item: item[0]):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def read_gate_nginx_reload_stamp(stack_root: Path) -> Optional[str]:
    """Fingerprint last successfully loaded into a running gate, if recorded."""
    path = stack_root / GATE_NGINX_RELOAD_STAMP
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def write_gate_nginx_reload_stamp(stack_root: Path, fingerprint: str) -> None:
    """Record that gate nginx has loaded this fingerprint (reload or cold start)."""
    path = stack_root / GATE_NGINX_RELOAD_STAMP
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fingerprint + "\n", encoding="utf-8")


class StackRenderer:
    def __init__(
        self,
        stack: Stack,
        *,
        edge: Optional[EdgeConfig] = None,
    ) -> None:
        self.stack = stack
        self.edge = edge if edge is not None else load_config(stack.root).edge

    @property
    def generated_root(self) -> Path:
        return self.stack.root / GENERATED_DIRNAME

    def compose_apps_path(self) -> Path:
        return self.generated_root / "compose.apps.yaml"

    def compose_edge_path(self) -> Path:
        return self.generated_root / "compose.edge.yaml"

    def router_hosts_path(self) -> Path:
        return self.generated_root / "nginx" / "router" / "hosts.conf"

    def gate_tls_dir(self) -> Path:
        return self.generated_root / "nginx" / "gate-tls"

    def gate_http_dir(self) -> Path:
        return self.generated_root / "nginx" / "gate-http"

    def gate_stream_dir(self) -> Path:
        return self.generated_root / "nginx" / "gate-stream"

    def load_all_specs(self) -> dict[str, AppSpec]:
        out: dict[str, AppSpec] = {}
        for app in self.stack.apps:
            _, app_spec = load_app_file(
                registry_path(self.stack.root, app.name),
                expect_name=app.name,
            )
            out[app.name] = app_spec
        return out

    def load_all_contracts(self) -> dict[str, AppSpec]:
        return self.load_all_specs()

    def render(self, specs: Optional[dict[str, AppSpec]] = None) -> None:
        resolved = specs if specs is not None else self.load_all_specs()
        for app in self.stack.apps:
            if app.name not in resolved:
                raise RuntimeError(
                    f"missing AppSpec for {app.name!r} "
                    f"(corrupt or incomplete registry entry).\n"
                    f"Fix: re-apply the app (`raft apply …`) or repair "
                    f"~/.raft/state/apps/{app.name}.yaml; then raft render"
                )
            self._validate_app_spec(app, resolved[app.name])

        fragments = EdgeFragments()
        tls = TlsEdge()
        for app in self.stack.apps:
            app_spec = resolved[app.name]
            fragments.merge(tls.contribute_app(app, app_spec, edge=self.edge))
            for port in app_spec.ports:
                handler = EDGE_HANDLERS[port.expose]
                fragments.merge(handler.contribute(app, app_spec, port, edge=self.edge))

        self.generated_root.mkdir(parents=True, exist_ok=True)
        (self.generated_root / "nginx" / "router").mkdir(parents=True, exist_ok=True)
        self.gate_tls_dir().mkdir(parents=True, exist_ok=True)
        self.gate_http_dir().mkdir(parents=True, exist_ok=True)
        self.gate_stream_dir().mkdir(parents=True, exist_ok=True)
        self.stack.upstreams_dir.mkdir(parents=True, exist_ok=True)

        self.compose_apps_path().write_text(
            self._compose_apps_yaml(resolved, fragments), encoding="utf-8"
        )
        self.compose_edge_path().write_text(self._compose_edge_yaml(), encoding="utf-8")
        self.router_hosts_path().write_text(self._router_hosts_conf(fragments), encoding="utf-8")
        self._write_gate_http(fragments)
        self._write_gate_stream(fragments)
        self._write_gate_tls(fragments)
        self._write_upstreams(fragments)

        logger.info(
            "rendered %s apps → %s",
            len(self.stack.apps),
            self.generated_root.relative_to(self.stack.root),
        )

    def _validate_app_spec(self, app: App, app_spec: AppSpec) -> None:
        if app.source in {"git", "local"} and not app_spec.build_context:
            raise ValueError(
                f"{app.name}: [spec.build].context is required when source={app.source}"
            )
        if app.source == "docker" and app_spec.build_context:
            logger.debug(
                "%s: source=docker ignores [spec.build] (image comes from inventory)",
                app.name,
            )

    def _compose_apps_yaml(
        self,
        specs: dict[str, AppSpec],
        fragments: EdgeFragments,
    ) -> str:
        if not self.stack.apps:
            return (
                "# Generated by `raft render` — do not edit.\n"
                "# Source: ~/.raft/state/apps/*.yaml (applied App manifests)\n"
                "services: {}\n"
            )

        host_by_app: dict[str, list[str]] = {a.name: [] for a in self.stack.apps}
        expose_by_app: dict[str, list[int]] = {a.name: [] for a in self.stack.apps}
        for app in self.stack.apps:
            app_spec = specs[app.name]
            for port in app_spec.ports:
                expose_by_app[app.name].append(port.container_port)
                if port.expose == "host":
                    public = port.public_port
                    assert public is not None
                    proto = "" if port.protocol == "tcp" else f"/{port.protocol}"
                    host_by_app[app.name].append(f'"{public}:{port.container_port}{proto}"')

        lines: list[str] = [
            "# Generated by `raft render` — do not edit.",
            "# Source: ~/.raft/state/apps/*.yaml (applied App manifests)",
            "services:",
            "  router:",
            "    depends_on:",
        ]
        for app in self.stack.apps:
            lines.append(f"      {app.name}:")
            lines.append("        condition: service_healthy")

        for app in self.stack.apps:
            c = specs[app.name]
            lines.append(f"  {app.name}:")
            if app.source == "docker":
                lines.append(f"    image: {app.compose_pin_image}")
            else:
                ctx = (app.abs_path(self.stack.root) / (c.build_context or ".")).resolve()
                try:
                    rel = ctx.relative_to(self.stack.root.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"{app.name}: build context {ctx} is outside raft data home"
                    ) from exc
                build_path = rel.as_posix()
                if c.dockerfile:
                    lines.append("    build:")
                    lines.append(f"      context: ./{build_path}")
                    lines.append(f"      dockerfile: {c.dockerfile}")
                else:
                    lines.append(f"    build: ./{build_path}")
            unique_expose = sorted(set(expose_by_app[app.name]))
            lines.append("    expose:")
            for port_num in unique_expose:
                lines.append(f'      - "{port_num}"')
            host_ports = host_by_app[app.name]
            if host_ports:
                lines.append("    ports:")
                for entry in host_ports:
                    lines.append(f"      - {entry}")
            strategy = ReadinessStrategy.from_spec(c)
            test = strategy.healthcheck_test()
            if test is not None:
                lines.append("    healthcheck:")
                quoted = ", ".join(f'"{part}"' for part in test)
                lines.append(f"      test: [{quoted}]")
                lines.append("      interval: 2s")
                lines.append("      timeout: 2s")
                lines.append("      retries: 15")
                lines.append("      start_period: 2s")
            lines.append("    restart: unless-stopped")
            lines.append("    deploy:")
            lines.append("      resources:")
            lines.append("        limits:")
            lines.append(f'          cpus: "{c.cpus_limit}"')
            lines.append(f"          memory: {c.memory_limit}")
            lines.append("        reservations:")
            lines.append(f'          cpus: "{c.cpus_reservation}"')
            lines.append(f"          memory: {c.memory_reservation}")
        lines.append("")
        return "\n".join(lines)

    def _compose_edge_yaml(self) -> str:
        lines = [
            "# Generated by `raft render` — gate published ports from settings edge:",
            "services:",
            "  gate:",
            "    ports:",
        ]
        published = self.edge.published_ports()
        if not published:
            lines.append("      []")
        else:
            for port, protocol in published:
                if protocol == "tcp":
                    lines.append(f'      - "{port}:{port}"')
                else:
                    lines.append(f'      - "{port}:{port}/{protocol}"')
        lines.append("")
        return "\n".join(lines)

    def _router_hosts_conf(self, fragments: EdgeFragments) -> str:
        blocks: list[str] = [
            "# Generated by `raft render` — do not edit.",
            "",
        ]
        blocks.extend(fragments.router_includes)
        if fragments.router_includes:
            blocks.append("")
        blocks.extend(fragments.router_servers)
        return "\n".join(blocks)

    def _write_gate_http(self, fragments: EdgeFragments) -> None:
        parts: list[str] = ["# Generated by raft render — gate http listeners\n"]
        if self.edge.http is not None:
            parts.append(
                "server {\n"
                f"    listen {self.edge.http} default_server;\n"
                "    server_name _;\n"
                "\n"
                "    include /etc/nginx/gate/proxy_router.inc;\n"
                "}\n"
            )
        if self.edge.https is not None:
            parts.append(
                "\n"
                "server {\n"
                f"    listen {self.edge.https} ssl default_server;\n"
                "    server_name _;\n"
                "    ssl_reject_handshake on;\n"
                "}\n"
            )
        path = self.gate_http_dir() / "listeners.conf"
        path.write_text("".join(parts), encoding="utf-8")
        keep = {"listeners.conf"}
        for stale in self.gate_http_dir().glob("*.conf"):
            if stale.name not in keep:
                stale.unlink()
                logger.info("removed stale gate-http %s", stale.name)

    def _write_gate_stream(self, fragments: EdgeFragments) -> None:
        body = "# Generated by raft render — gate stream servers\n\n"
        if fragments.gate_stream:
            body += "\n".join(fragments.gate_stream)
        else:
            body += "# (no stream ports)\n"
        path = self.gate_stream_dir() / "streams.conf"
        path.write_text(body, encoding="utf-8")
        keep = {"streams.conf"}
        for stale in self.gate_stream_dir().glob("*.conf"):
            if stale.name not in keep:
                stale.unlink()

    def _write_gate_tls(self, fragments: EdgeFragments) -> None:
        keep = set(fragments.gate_tls)
        for name, content in fragments.gate_tls.items():
            (self.gate_tls_dir() / name).write_text(content, encoding="utf-8")
        for path in self.gate_tls_dir().glob("*.conf"):
            if path.name not in keep:
                path.unlink()
                logger.info("removed stale generated TLS snippet %s", path.name)

    def _write_upstreams(self, fragments: EdgeFragments) -> None:
        keep = set(fragments.upstreams)
        for name, content in fragments.upstreams.items():
            (self.stack.upstreams_dir / name).write_text(content, encoding="utf-8")
        for path in self.stack.upstreams_dir.glob("*.conf"):
            if path.name not in keep:
                path.unlink()
                logger.info("removed stale upstream %s", path.name)
