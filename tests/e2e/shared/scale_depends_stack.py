"""Real-Docker harness: scaled frontend wake also starts dependsOn backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.controller.scale import Scaler
from raft.controller.wake_http import start_wake_http
from raft.models.scaling_spec import ScalingSpec
from raft.models.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.render import StackRenderer
from tests.e2e.shared.compose import new_project_name
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.e2e.shared.scale_stack import SCALING, ScaleE2EStack
from tests.shared.http import HttpResponse
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.wait import Wait
from tests.shared.yaml_doc import YamlDoc

FRONTEND = "stack-front"
BACKEND = "stack-redis"
FRONTEND_COMPOSE = "demo-stack-front"
BACKEND_COMPOSE = "demo-stack-redis"
PUBLIC_HOST = "front.test"


class ScaleDependsWakeStack:
    """Gate + grouped FE/BE; story helpers for dependsOn wake."""

    def __init__(self, inner: ScaleE2EStack) -> None:
        self._inner = inner
        self.docker = inner.docker
        self.store = ScalingStore(inner.home)

    @classmethod
    def create(cls, home: Path) -> "ScaleDependsWakeStack":
        project = new_project_name()
        cls._prepare_home(home)
        inner = cls._boot(home, project)
        return cls(inner)

    @classmethod
    def _boot(cls, home: Path, project: str) -> ScaleE2EStack:
        model = load_stack(home)
        docker = DockerStack(model, Shell(home))
        scaler = Scaler(home, docker)
        wake = start_wake_http(scaler, host="0.0.0.0", port=0)
        assert wake._httpd is not None
        wake_port = int(wake._httpd.server_address[1])
        ScaleE2EStack._rewrite_wake_port(home, wake_port)
        ScaleE2EStack._install_edge_compose(home, project)
        docker.sh.compose("up", "-d", "--pull", "missing", check=True, capture=True)
        gate_port = ScaleE2EStack._wait_gate_port(docker, timeout=60.0)
        inner = ScaleE2EStack(home, project, docker, scaler, wake_port, gate_port)
        inner._wake = wake
        return inner

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "ScaleDependsWakeStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def given_frontend_and_backend_are_running(self) -> None:
        ServiceRuntimeWait(self.docker, BACKEND_COMPOSE).until_running()
        ServiceRuntimeWait(self.docker, FRONTEND_COMPOSE).until_running()
        Wait.until(
            self._site_is_live,
            timeout=45.0,
            interval=0.5,
            message="site not live after cold start",
        )

    def when_the_backend_is_stopped(self) -> None:
        self.docker.stop_service(BACKEND_COMPOSE)
        ServiceRuntimeWait(self.docker, BACKEND_COMPOSE).until_stopped()

    def and_the_frontend_is_scaled_to_zero(self) -> None:
        self.docker.stop_service(FRONTEND_COMPOSE)
        self.store.mark_scaled_to_zero(FRONTEND)
        ServiceRuntimeWait(self.docker, FRONTEND_COMPOSE).until_stopped()

    def when_the_frontend_idle_stops(self) -> None:
        """Controller idle-stop: co-stops dependsOn (default scaleWithParent).

        Use ``idle_stop_now`` — not seed+``tick``. Async gate ``/activity`` can
        wipe a seeded ``lastActivityAt=0`` (or make tick load ``last is None``
        and reseed to tick time=3601). That is the CI fingerprint; see
        ``test_idle_activity_races.py``. Idle timing stays in unit tests.
        """
        self._inner.scaler.idle_stop_now(FRONTEND)
        if not self.store.is_scaled_to_zero(FRONTEND):
            raise AssertionError(self._idle_stop_debug())
        ServiceRuntimeWait(self.docker, FRONTEND_COMPOSE).until_stopped()
        ServiceRuntimeWait(self.docker, BACKEND_COMPOSE).until_stopped()

    def _idle_stop_debug(self) -> str:
        state = self.store.load(FRONTEND)
        front, fh = self.docker.service_runtime(FRONTEND_COMPOSE)
        back, bh = self.docker.service_runtime(BACKEND_COMPOSE)
        return (
            "idle-stop did not mark frontend scaledToZero "
            f"(last_activity={state.last_activity_at} min_up={state.min_up_until} "
            f"frontend={front}/{fh} backend={back}/{bh})"
        )

    def then_both_are_scaled_to_zero(self) -> None:
        assert self.store.is_scaled_to_zero(FRONTEND)
        assert self.store.is_scaled_to_zero(BACKEND)
        front, _ = self.docker.service_runtime(FRONTEND_COMPOSE)
        back, _ = self.docker.service_runtime(BACKEND_COMPOSE)
        assert front != "running", f"frontend status={front!r}"
        assert back != "running", f"backend status={back!r}"

    def visitor_sees_the_holding_page(self) -> bool:
        # Marker is authoritative; HTTP also triggers gate→wake (side effect).
        marker = self._inner.home / "state" / "scaling" / "markers" / f"{FRONTEND}.zero"
        if not marker.is_file():
            return False
        return "Starting" in self._curl().body

    def when_a_visitor_keeps_requesting_the_site(self) -> None:
        """Finish any gate-triggered wake, then sync wake_now + poll until live."""
        scaler = self._inner.scaler
        scaling = ScalingSpec(
            float(SCALING["idleSeconds"]),
            float(SCALING["wakeTimeoutSeconds"]),
            float(SCALING["minUpSeconds"]),
        )
        try:
            scaler.wait_wake_idle(timeout=float(SCALING["wakeTimeoutSeconds"]) + 30.0)
            if not self._fully_awake():
                assert scaler.wake_now(FRONTEND, scaling), self._wake_debug()
            Wait.until(
                self._poll_visitor_awake,
                timeout=float(SCALING["wakeTimeoutSeconds"]) + 30.0,
                interval=0.5,
                message="wake did not bring frontend+backend live",
            )
        except TimeoutError:
            raise TimeoutError(self._wake_debug()) from None

    def _poll_visitor_awake(self) -> bool:
        """Visitor meta-refresh: keep hitting the Host while waiting."""
        try:
            self._curl(expect_status=None)
        except OSError:
            pass
        return self._fully_awake()

    def _wake_debug(self) -> str:
        backend, bh = self.docker.service_runtime(BACKEND_COMPOSE)
        front, fh = self.docker.service_runtime(FRONTEND_COMPOSE)
        scaled = self.store.is_scaled_to_zero(FRONTEND)
        state = self.store.load(FRONTEND)
        fetch = self.docker.router_can_fetch(FRONTEND_COMPOSE, port=5678, path="/")
        host = self.docker.router_serves_host(PUBLIC_HOST, path="/")
        try:
            resp = self._curl(expect_status=None)
            site = f"status={resp.status} body={resp.body[:120]!r}"
        except OSError as exc:
            site = f"curl_err={exc}"
        return (
            "wake did not bring frontend+backend live "
            f"(backend={backend}/{bh} frontend={front}/{fh} scaled={scaled} "
            f"wake_req={state.wake_requested_at} timed_out={state.wake_timed_out} "
            f"fetch={fetch} host={host} {site})"
        )

    def then_the_backend_is_running(self) -> None:
        status, _ = self.docker.service_runtime(BACKEND_COMPOSE)
        assert status == "running", f"backend status={status!r}"

    def then_the_frontend_is_running(self) -> None:
        status, _ = self.docker.service_runtime(FRONTEND_COMPOSE)
        assert status == "running", f"frontend status={status!r}"
        assert not self.store.is_scaled_to_zero(FRONTEND)

    def then_the_site_serves_the_app(self) -> None:
        assert self._site_is_live()

    def _fully_awake(self) -> bool:
        backend, _ = self.docker.service_runtime(BACKEND_COMPOSE)
        front, _ = self.docker.service_runtime(FRONTEND_COMPOSE)
        if backend != "running" or front != "running":
            return False
        if self.store.is_scaled_to_zero(FRONTEND):
            return False
        return self._site_is_live()

    def _site_is_live(self) -> bool:
        try:
            resp = self._curl(expect_status=None)
        except OSError:
            return False
        bad = ("Starting", "Unavailable")
        return resp.status == 200 and not any(s in resp.body for s in bad)

    def _curl(self, *, expect_status: Optional[int] = 200) -> HttpResponse:
        return self._inner.http.get("/", host=PUBLIC_HOST, expect_status=expect_status)

    @classmethod
    def _prepare_home(cls, home: Path) -> None:
        yamls = RaftHomeFixtures.fixture_app_yamls("multi_app_group")
        ordered = sorted(yamls, key=lambda p: 0 if "redis" in str(p) else 1)
        RaftHomeFixtures.apply_and_render(home, ordered)
        YamlDoc(home / "state" / "apps" / f"{FRONTEND}.yaml").merge_spec(
            {"scaling": dict(SCALING)}
        )
        StackRenderer(load_stack(home)).render()
