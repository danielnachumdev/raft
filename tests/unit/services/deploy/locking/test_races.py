"""Upstream race and serialized deploy coverage."""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from raft.models.ports import PortSpec
from raft.services.deploy.locking import (
    ENV_LOCK_TIMEOUT,
    app_and_stack_locks,
    stack_lock,
)
from raft.services.deploy.orchestrator import Orchestrator
from raft.services.render import StackRenderer

from ....base import RaftTestCase, make_local_stack, write_applied_app
from ....cta_asserts import assert_operator


class TestUpstreamRaceWithoutLock(RaftTestCase):
    """Prove render can reset another app's mid-cutover upstream (unsafe without flock)."""

    @pytest.fixture(autouse=True)
    def _two_apps(self, _raft_base) -> None:
        write_applied_app(self.tmp_path, "alpha")
        write_applied_app(self.tmp_path, "beta", public_host="beta.test")
        self.stack = make_local_stack(self.tmp_path, "alpha", "beta", drain_seconds=0.0)
        StackRenderer(self.stack).render()
        self.alpha = self.stack.app("alpha")
        self.port = PortSpec(name="http", container_port=80, expose="http")

    def test_render_overwrites_tmp_upstream_without_serialization(self) -> None:
        from raft.adapters.nginx import NginxUpstreams

        docker = MagicMock()
        docker.router_sees_upstream_target.return_value = True
        nginx = NginxUpstreams(self.stack, docker)
        nginx.point_at(self.alpha, self.alpha.tmp_alias, port=self.port, reload=False)
        path = self.stack.upstream_file(self.alpha, self.port)
        assert self.alpha.tmp_alias in path.read_text(encoding="utf-8")
        StackRenderer(self.stack).render()
        text = path.read_text(encoding="utf-8")
        assert self.alpha.compose_id in text
        assert self.alpha.tmp_alias not in text

    def test_stack_lock_keeps_tmp_upstream_until_cutover_releases(self) -> None:
        from raft.adapters.nginx import NginxUpstreams

        docker = MagicMock()
        docker.router_sees_upstream_target.return_value = True
        nginx = NginxUpstreams(self.stack, docker)
        path = self.stack.upstream_file(self.alpha, self.port)
        done_render = threading.Event()
        saw_tmp = threading.Event()
        release_cutover = threading.Event()
        self._run_locked_cutover_and_render(nginx, saw_tmp, release_cutover, done_render)
        self._assert_tmp_held_then_steady(path, saw_tmp, release_cutover, done_render)

    def _run_locked_cutover_and_render(self, nginx, saw_tmp, release_cutover, done_render):
        def cutover_holder() -> None:
            with stack_lock(self.stack.root, timeout=5):
                nginx.point_at(self.alpha, self.alpha.tmp_alias, port=self.port, reload=False)
                saw_tmp.set()
                release_cutover.wait(timeout=5)

        def concurrent_render() -> None:
            assert saw_tmp.wait(timeout=2)
            with stack_lock(self.stack.root, timeout=5):
                StackRenderer(self.stack).render()
            done_render.set()

        self._t1 = threading.Thread(target=cutover_holder)
        self._t2 = threading.Thread(target=concurrent_render)
        self._t1.start()
        self._t2.start()

    def _assert_tmp_held_then_steady(self, path, saw_tmp, release_cutover, done_render):
        assert saw_tmp.wait(timeout=2)
        assert self.alpha.tmp_alias in path.read_text(encoding="utf-8")
        assert not done_render.is_set()
        release_cutover.set()
        self._t1.join(timeout=2)
        self._t2.join(timeout=2)
        assert done_render.is_set()
        assert self.alpha.compose_id in path.read_text(encoding="utf-8")


class TestSameAppLastFinisher(RaftTestCase):
    """Older slow deploy must not win when locks serialize; later deploy is final."""

    @pytest.fixture(autouse=True)
    def _app(self, _raft_base) -> None:
        write_applied_app(self.tmp_path, "app")
        self.stack = make_local_stack(self.tmp_path, drain_seconds=0.0)
        self.live: list[str] = []

    def test_serialized_deploys_later_started_wins(self) -> None:
        started_b = threading.Event()
        a_holds = threading.Event()

        def deploy_a() -> None:
            with app_and_stack_locks(self.stack.root, "app", timeout=5):
                a_holds.set()
                assert started_b.wait(timeout=2)
                time.sleep(0.05)
                self.live.append("image-A-old")

        def deploy_b() -> None:
            assert a_holds.wait(timeout=2)
            started_b.set()
            with app_and_stack_locks(self.stack.root, "app", timeout=5):
                self.live.append("image-B-new")

        self._join_pair(deploy_a, deploy_b, timeout=3)
        assert self.live == ["image-A-old", "image-B-new"]

    def _join_pair(self, a, b, *, timeout: float) -> None:
        t_a = threading.Thread(target=a)
        t_b = threading.Thread(target=b)
        t_a.start()
        t_b.start()
        t_a.join(timeout=timeout)
        t_b.join(timeout=timeout)

    def test_overlapping_without_lock_last_finisher_can_be_stale(self) -> None:
        barrier = threading.Barrier(2)
        finish_order: list[str] = []

        def slow_old() -> None:
            barrier.wait(timeout=2)
            time.sleep(0.1)
            self.live[:] = ["image-A-old"]
            finish_order.append("A")

        def fast_new() -> None:
            barrier.wait(timeout=2)
            time.sleep(0.01)
            self.live[:] = ["image-B-new"]
            finish_order.append("B")

        self._join_pair(slow_old, fast_new, timeout=2)
        assert finish_order == ["B", "A"]
        assert self.live == ["image-A-old"]


class TestOrchestratorUsesLocks(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _orch(self, _raft_base) -> None:
        write_applied_app(self.tmp_path, "app")
        self.stack = make_local_stack(self.tmp_path, drain_seconds=0.0)
        self.orch = Orchestrator(self.stack)
        self.orch.docker = MagicMock()
        self.orch.nginx = MagicMock()
        self.orch.http = MagicMock()
        self.orch.syncer = MagicMock()

    def test_render_waits_on_held_stack_lock(self) -> None:
        held = threading.Event()
        release = threading.Event()
        errors: list[BaseException] = []
        self._start_holder_and_renderer(held, release, errors)
        assert errors

        assert_operator(errors[0], contains=("stack", "RAFT_LOCK_TIMEOUT_SECONDS"))

    def _start_holder_and_renderer(self, held, release, errors) -> None:
        def holder() -> None:
            with stack_lock(self.stack.root, timeout=5):
                held.set()
                release.wait(timeout=5)

        def renderer() -> None:
            try:
                assert held.wait(timeout=2)
                with patch.dict(os.environ, {ENV_LOCK_TIMEOUT: "0.2"}):
                    self.orch.render()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=renderer)
        t1.start()
        t2.start()
        t2.join(timeout=3)
        release.set()
        t1.join(timeout=2)
