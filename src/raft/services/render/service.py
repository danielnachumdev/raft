"""Render Compose + nginx fragments from applied App manifests + edge settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from raft.errors import OperatorError

from ...config.paths import GENERATED_DIRNAME
from ...config.settings import load_config
from ...config.settings_types import EdgeConfig
from ...models.app import App
from ...models.app_document import AppDocument
from ...models.manifest import AppSpec
from ...models.registry import AppRegistry
from ...models.stack import Stack
from .compose_apps import ComposeAppsYaml
from .edge import EDGE_HANDLERS, EdgeFragments, TlsEdge
from .scaling_gate import ScalingGate

logger = logging.getLogger(__name__)


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
            _, app_spec = AppDocument.load(
                AppRegistry(self.stack.root).path_for(app.name),
                expect_name=app.name,
            )
            out[app.name] = app_spec
        return out

    def load_all_contracts(self) -> dict[str, AppSpec]:
        return self.load_all_specs()

    def render(self, specs: Optional[dict[str, AppSpec]] = None) -> None:
        resolved = specs if specs is not None else self.load_all_specs()
        self._validate_all(resolved)
        fragments = self._collect_fragments(resolved)
        self._ensure_dirs()
        self._write_all(resolved, fragments)
        logger.info(
            "rendered %s apps → %s",
            len(self.stack.apps),
            self.generated_root.relative_to(self.stack.root),
        )

    def _validate_all(self, resolved: dict[str, AppSpec]) -> None:
        for app in self.stack.apps:
            if app.name not in resolved:
                raise OperatorError(
                    f"missing AppSpec for {app.name!r} "
                    f"(corrupt or incomplete registry entry).\n"
                    f"Fix: re-apply the app (`raft apply …`) or repair "
                    f"~/.raft/state/apps/{app.name}.yaml; then raft render"
                )
            self._validate_app_spec(app, resolved[app.name])

    def _collect_fragments(self, resolved: dict[str, AppSpec]) -> EdgeFragments:
        fragments = EdgeFragments()
        tls = TlsEdge()
        scaling = ScalingGate()
        for app in self.stack.apps:
            app_spec = resolved[app.name]
            fragments.merge(self._tls_fragment(tls, scaling, app, app_spec))
            for port in app_spec.ports:
                handler = EDGE_HANDLERS[port.expose]
                fragments.merge(handler.contribute(app, app_spec, port, edge=self.edge))
            fragments.merge(scaling.contribute_http(app, app_spec, edge=self.edge))
        return fragments

    def _tls_fragment(
        self,
        tls: TlsEdge,
        scaling: ScalingGate,
        app: App,
        app_spec: AppSpec,
    ) -> EdgeFragments:
        if app_spec.tls == "origin" and app_spec.scaling is not None:
            if self.edge.https is None:
                raise OperatorError(
                    f"{app.name}: tls=origin requires edge.https in settings.yaml.\n"
                    f"Fix: set edge.https (e.g. 443) in ~/.raft/settings.yaml, then: raft render"
                )
            body = scaling.contribute_tls(app, app_spec)
            return EdgeFragments(gate_tls={f"{app.name}.conf": body})
        return tls.contribute_app(app, app_spec, edge=self.edge)

    def _ensure_dirs(self) -> None:
        self.generated_root.mkdir(parents=True, exist_ok=True)
        (self.generated_root / "nginx" / "router").mkdir(parents=True, exist_ok=True)
        self.gate_tls_dir().mkdir(parents=True, exist_ok=True)
        self.gate_http_dir().mkdir(parents=True, exist_ok=True)
        self.gate_stream_dir().mkdir(parents=True, exist_ok=True)
        self.stack.upstreams_dir.mkdir(parents=True, exist_ok=True)

    def _write_all(self, resolved: dict[str, AppSpec], fragments: EdgeFragments) -> None:
        self.compose_apps_path().write_text(
            ComposeAppsYaml(self.stack).build(resolved, fragments), encoding="utf-8"
        )
        self.compose_edge_path().write_text(self._compose_edge_yaml(), encoding="utf-8")
        self.router_hosts_path().write_text(self._router_hosts_conf(fragments), encoding="utf-8")
        self._write_gate_http(fragments)
        self._write_gate_stream(fragments)
        self._write_gate_tls(fragments)
        self._write_upstreams(fragments)

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

    def _compose_edge_yaml(self) -> str:
        lines = [
            "# Generated by `raft render` — gate published ports from settings edge:",
            "services:",
            f"  {self.stack.gate}:",
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
        parts.extend(fragments.gate_http)
        if fragments.gate_http:
            parts.append("\n")
        parts.extend(self._gate_http_servers())
        path = self.gate_http_dir() / "listeners.conf"
        path.write_text("".join(parts), encoding="utf-8")
        self._prune_conf_dir(self.gate_http_dir(), keep={"listeners.conf"}, label="gate-http")

    def _gate_http_servers(self) -> list[str]:
        parts: list[str] = []
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
        return parts

    def _write_gate_stream(self, fragments: EdgeFragments) -> None:
        body = "# Generated by raft render — gate stream servers\n\n"
        if fragments.gate_stream:
            body += "\n".join(fragments.gate_stream)
        else:
            body += "# (no stream ports)\n"
        path = self.gate_stream_dir() / "streams.conf"
        path.write_text(body, encoding="utf-8")
        self._prune_conf_dir(self.gate_stream_dir(), keep={"streams.conf"}, label=None)

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

    @staticmethod
    def _prune_conf_dir(directory: Path, *, keep: set[str], label: Optional[str]) -> None:
        for stale in directory.glob("*.conf"):
            if stale.name in keep:
                continue
            stale.unlink()
            if label:
                logger.info("removed stale %s %s", label, stale.name)
