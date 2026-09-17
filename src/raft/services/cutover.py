"""App redeploy cutover plan (previous-image tmp → stable)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from raft.errors import OperatorError

from ..adapters.docker import DockerStack
from ..adapters.http import HttpProbe
from ..adapters.nginx import NginxUpstreams
from ..models.app import COMPOSE_PROJECT, App
from ..models.stack import Stack
from .readiness import ReadinessStrategy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Step:
    key: str
    summary: str
    run: Callable[["CutoverSession"], None]


def wait_until(
    description: str,
    predicate: Callable[[], bool],
    *,
    timeout: float,
    interval: float = 1.0,
    fix: str = "",
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    logger.error("timed out waiting for: %s", description)
    message = f"timed out waiting for: {description}"
    if fix:
        message = f"{message}\nFix: {fix}"
    raise OperatorError(message, has_fix=bool(fix))


@dataclass
class CutoverSession:
    stack: Stack
    app: App
    docker: DockerStack
    nginx: NginxUpstreams
    http: HttpProbe
    previous_image: Optional[str] = None
    network: str = f"{COMPOSE_PROJECT}_default"

    def log(self, message: str) -> None:
        logger.info("%s", message)

    def _strategy(self) -> ReadinessStrategy:
        return ReadinessStrategy.from_spec(self.stack.spec_for(self.app))

    def _wait_ready(self, label: str, *, timeout: float = 30) -> None:
        strategy = self._strategy()
        predicate = strategy.wait_predicate(self.app, self.stack, self.http)
        if predicate is None:
            return
        wait_until(
            label,
            predicate,
            timeout=timeout,
            interval=0.5,
            fix=(
                f"check readiness/health for {self.app.name}; "
                f"raft doctor; raft redeploy {self.app.name}"
            ),
        )

    def snapshot_previous_image(self) -> None:
        cid = self.docker.service_container_id(self.app.name)
        image_ref = self.docker.container_image_ref(cid)
        self.previous_image = image_ref
        image_id = self.docker.container_image_id(cid)
        state = self.stack.image_state_file(self.app)
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(f"{image_id}\n# ref: {image_ref}\n", encoding="utf-8")
        self.network = self.docker.router_network()
        self.log(f"previous image saved: {image_ref} ({image_id})")

    def start_tmp_from_previous(self) -> None:
        assert self.previous_image
        self.log(f"start {self.app.tmp_alias} from previous image")
        self.docker.run_tmp(
            name=self.app.tmp_container,
            alias=self.app.tmp_alias,
            image=self.previous_image,
            network=self.network,
        )
        strategy = self._strategy()
        if strategy.kind == "http":
            fetch_port = strategy.port.container_port if strategy.port is not None else 80
            wait_until(
                f"{self.app.tmp_alias} reachable from router",
                lambda: self.docker.router_can_fetch(self.app.tmp_alias, port=fetch_port),
                timeout=self.stack.ready_timeout_seconds,
                fix=(
                    f"inspect tmp container / upstreams; then: "
                    f"raft redeploy {self.app.name} or raft doctor"
                ),
            )

    def shift_traffic_to_tmp(self) -> None:
        self.log(f"point nginx at {self.app.tmp_alias} (old code) + reload + drain")
        self.nginx.point_at(self.app, self.app.tmp_alias)
        self.docker.nginx_test_and_reload()
        self._wait_ready(f"readiness for {self.app.name} via tmp")
        time.sleep(self.stack.drain_seconds)

    def rebuild_stable_service(self) -> None:
        if self.app.source == "docker":
            pull_ref = self.app.image_ref(self._docker_wanted_tag())
            self.log(f"pull/recreate stable service {self.app.name} ({pull_ref})")
            self.docker.recreate_pulled_service(self.app, pull_ref=pull_ref)
        else:
            self.log(f"rebuild stable service {self.app.name} (new code)")
            self.docker.rebuild_service(self.app.name)
        strategy = self._strategy()
        if strategy.kind == "http":
            fetch_port = strategy.port.container_port if strategy.port is not None else 80
            wait_until(
                f"{self.app.name} reachable from router",
                lambda: self.docker.router_can_fetch(self.app.name, port=fetch_port),
                timeout=self.stack.ready_timeout_seconds,
                fix=(
                    f"check build/pull logs; traffic may still be on "
                    f"{self.app.name}_tmp — raft doctor / raft redeploy {self.app.name}"
                ),
            )

    def _docker_wanted_tag(self) -> str:
        state = self.stack.ref_state_file(self.app)
        try:
            lines = state.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return self.app.ref
        for line in lines:
            if line.startswith("# requested:"):
                parsed = line.split(":", 1)[1].strip()
                return parsed or self.app.ref
        return self.app.ref

    def shift_traffic_to_stable(self) -> None:
        self.log(f"point nginx at {self.app.name} (new code) + reload + drain")
        self.nginx.point_at(self.app, self.app.name)
        self.docker.nginx_test_and_reload()
        self._wait_ready(f"readiness for {self.app.name} via stable")
        time.sleep(self.stack.drain_seconds)

    def remove_tmp(self) -> None:
        self.log(f"remove temp {self.app.tmp_container}")
        self.docker.remove_container(self.app.tmp_container)
        cid = self.docker.service_container_id(self.app.name)
        new_image = self.docker.container_image_id(cid)
        self.stack.image_state_file(self.app).write_text(new_image + "\n", encoding="utf-8")
        self.log(f"done: {self.app.name} live on {new_image}")


DEPLOY_CUTOVER: tuple[Step, ...] = (
    Step(
        "snapshot_previous_image",
        "Remember the currently running image hash",
        CutoverSession.snapshot_previous_image,
    ),
    Step(
        "start_tmp_from_previous",
        "Run that hash as <app>_tmp",
        CutoverSession.start_tmp_from_previous,
    ),
    Step(
        "shift_traffic_to_tmp",
        "Nginx → tmp, reload, drain",
        CutoverSession.shift_traffic_to_tmp,
    ),
    Step(
        "rebuild_stable_service",
        "Build/recreate the stable Compose service",
        CutoverSession.rebuild_stable_service,
    ),
    Step(
        "shift_traffic_to_stable",
        "Nginx → stable name, reload, drain",
        CutoverSession.shift_traffic_to_stable,
    ),
    Step("remove_tmp", "Delete the temporary container", CutoverSession.remove_tmp),
)
