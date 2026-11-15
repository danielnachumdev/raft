"""Full App delete: registry + durable tree + Compose unit + local auth."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from raft.core.core.config.paths.service_paths import ServicePaths
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.app import App
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.stack import Stack, load_stack
from raft.core.core.ui import OperatorSay
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.adapters.shell import Shell
from raft.core.platform.auth import GitAuthManager
from raft.core.platform.locking import AppAndStackLocks
from raft.core.platform.locking.paths import LockPaths

logger = logging.getLogger(__name__)


class AppDelete:
    """Remove an applied App end-to-end (not just ``app.yaml``)."""

    def __init__(
        self,
        stack: Stack,
        *,
        docker: Optional[DockerStack] = None,
        auth: Optional[GitAuthManager] = None,
    ) -> None:
        self.stack = stack
        self._docker = docker
        self._auth = auth

    def run(self, name: str) -> None:
        with AppAndStackLocks(self.stack.root, name):
            app = self._require_applied(name)
            self._remove_compose(app)
            if not AppRegistry(self.stack.root).delete(name):
                known = ", ".join(a.name for a in self.stack.apps) or "(none)"
                raise DomainErrors.app_not_applied(name, known)
            self._remove_durable_tree(name)
            self._remove_local_auth(name)
            self._remove_host_job_artifacts(name)
            OperatorSay.say(f"deleted {name} from registry", style="ok")
            fresh = load_stack(self.stack.root)
            Orchestrator(fresh).render()
            self._announce(name, fresh)

    def _require_applied(self, name: str) -> App:
        path = AppRegistry(self.stack.root).path_for(name)
        if not path.is_file():
            known = ", ".join(a.name for a in self.stack.apps) or "(none)"
            raise DomainErrors.app_not_applied(name, known)
        for app in self.stack.apps:
            if app.name == name:
                return app
        # YAML present but skipped at load — still delete the durable name.
        return App(name=name, public_host="", source="local", path="")

    def _remove_compose(self, app: App) -> None:
        compose_id = app.compose_id
        try:
            self._docker_stack().remove_service(compose_id)
            OperatorSay.say(f"removed Compose service {compose_id}", style="ok")
        except Exception as exc:  # noqa: BLE001 — best-effort; render follows
            logger.warning("compose remove %s skipped: %s", compose_id, exc)
            OperatorSay.say(
                f"could not remove Compose service {compose_id} "
                f"(will drop from generated/ on render): {exc}",
                style="warn",
            )

    def _remove_durable_tree(self, name: str) -> None:
        root = ServicePaths(self.stack.root, name).root()
        if not root.exists():
            return
        shutil.rmtree(root, ignore_errors=True)
        if root.exists():
            OperatorSay.say(
                f"could not fully remove {root.relative_to(self.stack.root)}",
                style="warn",
            )
            return
        OperatorSay.say(
            f"removed durable tree services/{name}/",
            style="ok",
        )

    def _remove_local_auth(self, name: str) -> None:
        auth = self._auth if self._auth is not None else GitAuthManager(self.stack)
        if not auth.is_configured(name):
            return
        try:
            auth.remove(name, remove_files=True)
        except Exception as exc:  # noqa: BLE001 — delete must not abort mid-way
            logger.warning("auth remove %s skipped: %s", name, exc)
            OperatorSay.say(
                f"local deploy key for {name} not removed: {exc}",
                style="warn",
            )

    def _remove_host_job_artifacts(self, name: str) -> None:
        paths = LockPaths(self.stack.root)
        kind = f"redeploy-{name}"
        self._unlink(paths.host_job_flight(kind))
        fifo = paths.fifo(kind)
        if fifo.is_dir():
            shutil.rmtree(fifo, ignore_errors=True)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("lock cleanup %s skipped: %s", path, exc)

    def _docker_stack(self) -> DockerStack:
        if self._docker is not None:
            return self._docker
        return DockerStack(self.stack, Shell(self.stack.root))

    @staticmethod
    def _announce(name: str, fresh: Stack) -> None:
        if fresh.apps:
            OperatorSay.say(
                f"re-rendered generated/ after deleting {name}",
                style="info",
            )
        else:
            OperatorSay.say("re-rendered generated/ (no apps applied)", style="info")
