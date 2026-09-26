"""App redeploy cutover plan (previous-image tmp → stable)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ..adapters.docker import DockerStack
from ..adapters.http import HttpProbe
from ..adapters.nginx import NginxUpstreams
from ..models.app import COMPOSE_PROJECT, App
from ..models.stack import Stack
from .readiness import ReadinessStrategy
from .wait import Step, wait_until

logger = logging.getLogger(__name__)


@dataclass
class CutoverSession:
    stack: Stack
    app: App
    docker: DockerStack
    nginx: NginxUpstreams
    http: HttpProbe
    previous_image: Optional[str] = None
    network: str = f"{COMPOSE_PROJECT}_default"
    # True after tmp is started until remove_tmp / abort_cleanup succeeds.
    tmp_active: bool = False

    def log(self, message: str) -> None:
        logger.info("%s", message)

    def _strategy(self) -> ReadinessStrategy:
        return ReadinessStrategy.from_spec(self.stack.spec_for(self.app))

    def _app_diagnostics(self) -> str:
        return self.docker.diagnostics_for(self.app.compose_id)

    def _tmp_diagnostics(self) -> str:
        return self.docker.diagnostics_for(
            containers=(self.app.tmp_container,),
        )

    def _wait_ready(self, label: str, *, timeout: Optional[float] = None) -> None:
        strategy = self._strategy()
        predicate = strategy.wait_predicate(
            self.app,
            self.stack,
            self.http,
            compose_ready=lambda: self.docker.service_is_ready(self.app.compose_id),
        )
        if predicate is None:
            return
        wait_budget = timeout if timeout is not None else strategy.timeout_seconds
        wait_until(
            label,
            predicate,
            timeout=wait_budget,
            interval=0.5,
            fix=self._ready_fix(strategy),
            diagnostics=self._app_diagnostics,
        )

    def _ready_fix(self, strategy: ReadinessStrategy) -> str:
        return (
            f"check readiness/health for {self.app.name}; "
            f"raft doctor; raft redeploy {self.app.name}. "
            f"If Compose health stays 'starting'/'unhealthy', inspect logs "
            f"and raise readiness.timeoutSeconds (and optionally "
            f"startPeriodSeconds) in .raft/app.yaml "
            f"[{strategy.timing_summary()}]"
        )

    def snapshot_previous_image(self) -> None:
        cid = self.docker.service_container_id(self.app.compose_id)
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
        spec = self.stack.spec_for(self.app)
        self.docker.run_tmp(
            name=self.app.tmp_container,
            alias=self.app.tmp_alias,
            image=self.previous_image,
            network=self.network,
            env_file=spec.env_file,
        )
        self.tmp_active = True
        self._wait_tmp_reachable()

    def _wait_tmp_reachable(self) -> None:
        strategy = self._strategy()
        if strategy.kind != "http":
            return
        fetch_port = strategy.port.container_port if strategy.port is not None else 80
        wait_until(
            f"{self.app.tmp_alias} reachable from router",
            lambda: self.docker.router_can_fetch(
                self.app.tmp_alias, port=fetch_port, path=strategy.path
            ),
            timeout=strategy.timeout_seconds,
            fix=(
                f"inspect tmp container / upstreams; then: "
                f"raft redeploy {self.app.name} or raft doctor "
                f"[{strategy.timing_summary()}]"
            ),
            diagnostics=self._tmp_diagnostics,
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
            self.docker.rebuild_service(self.app.compose_id)
        self._wait_stable_reachable()

    def _wait_stable_reachable(self) -> None:
        strategy = self._strategy()
        if strategy.kind != "http":
            return
        fetch_port = strategy.port.container_port if strategy.port is not None else 80
        wait_until(
            f"{self.app.compose_id} reachable from router",
            lambda: self.docker.router_can_fetch(
                self.app.compose_id, port=fetch_port, path=strategy.path
            ),
            timeout=strategy.timeout_seconds,
            fix=(
                f"check build/pull logs; traffic may still be on "
                f"{self.app.tmp_alias} — raft doctor / raft redeploy "
                f"{self.app.name} [{strategy.timing_summary()}]"
            ),
            diagnostics=self._app_diagnostics,
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
        self.log(f"point nginx at {self.app.compose_id} (new code) + reload + drain")
        self.nginx.point_at(self.app, self.app.compose_id)
        self.docker.nginx_test_and_reload()
        self._wait_ready(f"readiness for {self.app.name} via stable")
        time.sleep(self.stack.drain_seconds)

    def remove_tmp(self) -> None:
        self.log(f"remove temp {self.app.tmp_container}")
        self.docker.remove_container(self.app.tmp_container)
        self.tmp_active = False
        cid = self.docker.service_container_id(self.app.compose_id)
        new_image = self.docker.container_image_id(cid)
        self.stack.image_state_file(self.app).write_text(new_image + "\n", encoding="utf-8")
        self.log(f"done: {self.app.name} live on {new_image}")

    def abort_cleanup(self) -> None:
        """Best-effort restore after a failed cutover: stable upstream + drop tmp.

        Idempotent. Safe to call when tmp was never started.
        """
        if not self.tmp_active:
            # Still rm in case a prior crash left a container without flipping the flag
            # on a resumed process — only when we know cutover started tmp this session.
            return
        self.log(
            f"cutover abort cleanup: restore nginx → {self.app.compose_id}, "
            f"remove {self.app.tmp_container}"
        )
        self._abort_restore_nginx()
        self._abort_remove_tmp()

    def _abort_restore_nginx(self) -> None:
        try:
            self.nginx.point_at(self.app, self.app.compose_id)
            self.docker.nginx_test_and_reload()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            logger.warning(
                "abort cleanup: could not point nginx at %s",
                self.app.compose_id,
                exc_info=True,
            )

    def _abort_remove_tmp(self) -> None:
        try:
            self.docker.remove_container(self.app.tmp_container)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            logger.warning(
                "abort cleanup: could not remove %s",
                self.app.tmp_container,
                exc_info=True,
            )
        else:
            self.tmp_active = False


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
