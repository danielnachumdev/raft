"""Render Compose + nginx fragments from applied App manifests + edge settings."""

import logging
from pathlib import Path
from typing import Optional

from raft.core.core.config.paths import GENERATED_DIRNAME
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.stack import Stack
from .fragment_collector import FragmentCollector
from .generated_writer import GeneratedWriter
from .scaling_holding import ScalingHoldingPages

logger = logging.getLogger(__name__)


class StackRenderer:
    def __init__(
        self,
        stack: Stack,
        *,
        edge: Optional[EdgeConfig] = None,
    ) -> None:
        self.stack = stack
        self.edge = edge if edge is not None else SettingsLoader().load(stack.root).edge

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
        apps = list(self.stack.apps)
        fragments = FragmentCollector(root=self.stack.root, edge=self.edge).collect(
            apps, resolved
        )
        self._ensure_dirs()
        ScalingHoldingPages().install(self.stack.root, apps, resolved)
        GeneratedWriter(self.stack, self.edge).write_all(resolved, fragments)
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
                    f"~/.raft/services/*/{app.name}.yaml; then raft render"
                )
            self._validate_app_spec(app, resolved[app.name])

    def _ensure_dirs(self) -> None:
        self.generated_root.mkdir(parents=True, exist_ok=True)
        (self.generated_root / "nginx" / "router").mkdir(parents=True, exist_ok=True)
        self.gate_tls_dir().mkdir(parents=True, exist_ok=True)
        self.gate_http_dir().mkdir(parents=True, exist_ok=True)
        self.gate_stream_dir().mkdir(parents=True, exist_ok=True)
        self.stack.upstreams_dir.mkdir(parents=True, exist_ok=True)

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
