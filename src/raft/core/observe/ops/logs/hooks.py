"""Best-effort final drain before container remove / recreate."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import ServiceLogsConfig
from raft.core.core.models.stack import Stack

from .capture import ServiceLogsCapture
from .docker_source import DockerContainerLogSource
from .keys import ServiceLogsKeys
from .store import ServiceLogsStore

if TYPE_CHECKING:
    from raft.core.platform.adapters.docker.stack import DockerStack

logger = logging.getLogger(__name__)


class ServiceLogsHooks:
    """Lifecycle hooks shared by CLI and serve (via ``DockerStack``)."""

    @classmethod
    def before_compose_recreate(
        cls,
        stack: Stack,
        compose_id: str,
        docker: Optional["DockerStack"] = None,
    ) -> None:
        """Drain the running Compose service before force-recreate."""
        cls._safe(lambda: cls._drain_compose(stack, compose_id, docker))

    @classmethod
    def before_container_remove(
        cls,
        stack: Stack,
        container_name: str,
        docker: Optional["DockerStack"] = None,
    ) -> None:
        """Drain a named container (stable or cutover tmp) before ``rm``."""
        cls._safe(
            lambda: cls._drain_named(
                stack, container_name=container_name, docker=docker
            )
        )

    @classmethod
    def before_stack_down(
        cls, stack: Stack, docker: Optional["DockerStack"] = None
    ) -> None:
        """Drain every known Compose service before ``compose down``."""
        cls._safe(lambda: cls._drain_all(stack, docker))

    @staticmethod
    def _safe(action) -> None:
        try:
            action()
        except Exception as exc:  # noqa: BLE001 — never block recreate/rm
            logger.debug("service-logs drain skipped err=%s", exc)

    @classmethod
    def _drain_compose(
        cls,
        stack: Stack,
        compose_id: str,
        docker: Optional["DockerStack"],
    ) -> None:
        engine = cls._docker(stack, docker)
        cfg = cls._config(stack.root)
        if not cfg.enabled or not compose_id:
            return
        cid = engine.try_service_container_id(compose_id)
        if not cid:
            return
        cls._capture(stack.root, cfg, engine, stack=stack).ship(compose_id, cid)

    @classmethod
    def _drain_named(
        cls,
        stack: Stack,
        *,
        container_name: str,
        docker: Optional["DockerStack"],
    ) -> None:
        engine = cls._docker(stack, docker)
        cfg = cls._config(stack.root)
        if not cfg.enabled or not container_name:
            return
        key = ServiceLogsKeys(stack).key_for_container_name(container_name)
        if key is None:
            key = container_name
        cls._capture(stack.root, cfg, engine, stack=stack).ship(key, container_name)

    @classmethod
    def _drain_all(cls, stack: Stack, docker: Optional["DockerStack"]) -> None:
        cfg = cls._config(stack.root)
        if not cfg.enabled:
            return
        engine = cls._docker(stack, docker)
        capture = cls._capture(stack.root, cfg, engine, stack=stack)
        keys = ServiceLogsKeys(stack)
        for compose_id in keys.known_compose_ids(include_edge=cfg.include_edge):
            cid = engine.try_service_container_id(compose_id)
            if cid:
                capture.ship(compose_id, cid)

    @staticmethod
    def _config(home: Path) -> ServiceLogsConfig:
        return SettingsLoader().load(home).service_logs

    @staticmethod
    def _docker(stack: Stack, docker: Optional["DockerStack"]) -> "DockerStack":
        if docker is not None:
            return docker
        from raft.core.platform.adapters.docker.stack import DockerStack
        from raft.core.platform.adapters.shell import Shell

        return DockerStack(stack, Shell(stack.root))

    @classmethod
    def _capture(
        cls,
        home: Path,
        cfg: ServiceLogsConfig,
        docker: "DockerStack",
        *,
        stack: Optional[Stack] = None,
    ) -> ServiceLogsCapture:
        apps = stack.apps if stack is not None else ()
        store = ServiceLogsStore(
            home,
            max_age_days=cfg.retention_max_age_days,
            max_bytes=cfg.retention_max_bytes,
            compose_to_app=ServiceLogsStore.compose_map_from_apps(apps),
        )
        return ServiceLogsCapture(
            store,
            DockerContainerLogSource(
                docker,
                timeout=cfg.fetch_timeout_seconds,
                max_bytes=cfg.max_fetch_bytes,
                bootstrap_tail=cfg.max_fetch_lines,
            ),
        )
