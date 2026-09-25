"""Deploy / render concurrency locks (flock under ~/.raft/state/locks/)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.errors import OperatorError
from raft.models.ports import PortSpec
from raft.services.locking import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    ENV_LOCK_TIMEOUT,
    app_and_stack_locks,
    app_deploy_lock,
    app_lock_path,
    exclusive_lock,
    resolve_lock_timeout,
    stack_lock,
    stack_lock_path,
)
from raft.services.orchestrator import Orchestrator
from raft.services.render import StackRenderer

from ..base import RaftTestCase, make_local_stack, write_applied_app


class TestResolveLockTimeout:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_LOCK_TIMEOUT, raising=False)
        assert resolve_lock_timeout() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_override_arg(self) -> None:
        assert resolve_lock_timeout(1.5) == 1.5

    def test_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "12")
        assert resolve_lock_timeout() == 12.0

    def test_invalid_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "nope")
        with pytest.raises(OperatorError, match="RAFT_LOCK_TIMEOUT_SECONDS"):
            resolve_lock_timeout()

    def test_blank_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "  ")
        assert resolve_lock_timeout() == DEFAULT_LOCK_TIMEOUT_SECONDS

    def test_negative_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_LOCK_TIMEOUT, "-5")
        with pytest.raises(OperatorError, match="non-negative"):
            resolve_lock_timeout()

    def test_negative(self) -> None:
        with pytest.raises(OperatorError, match="non-negative"):
            resolve_lock_timeout(-1)


class TestExclusiveLock(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _lock_home(self, _raft_base) -> None:
        self.root = self.tmp_path

    def test_reentrant_same_process(self) -> None:
        path = stack_lock_path(self.root)
        with exclusive_lock(path, kind="stack", timeout=1):
            with exclusive_lock(path, kind="stack", timeout=1):
                assert path.is_file()

    def test_busy_times_out(self) -> None:
        path = stack_lock_path(self.root)
        held = threading.Event()
        release = threading.Event()

        def holder() -> None:
            with exclusive_lock(path, kind="stack", timeout=5):
                held.set()
                release.wait(timeout=5)

        thread = threading.Thread(target=holder)
        thread.start()
        assert held.wait(timeout=2)
        with pytest.raises(OperatorError, match="holds the stack lock"):
            with exclusive_lock(path, kind="stack", timeout=0.15):
                pass
        release.set()
        thread.join(timeout=2)

    def test_waiter_runs_after_holder(self) -> None:
        path = stack_lock_path(self.root)
        order: list[str] = []
        held = threading.Event()
        release = threading.Event()

        def slow() -> None:
            with exclusive_lock(path, kind="stack", timeout=5):
                order.append("A-start")
                held.set()
                release.wait(timeout=5)
                order.append("A-end")

        def later() -> None:
            assert held.wait(timeout=2)
            with exclusive_lock(path, kind="stack", timeout=5):
                order.append("B")

        t_a = threading.Thread(target=slow)
        t_b = threading.Thread(target=later)
        t_a.start()
        t_b.start()
        time.sleep(0.05)
        release.set()
        t_a.join(timeout=2)
        t_b.join(timeout=2)
        assert order == ["A-start", "A-end", "B"]

    def test_app_and_stack_helpers(self) -> None:
        with app_and_stack_locks(self.root, "web", timeout=1):
            assert app_lock_path(self.root, "web").is_file()
            assert stack_lock_path(self.root).is_file()
        with app_deploy_lock(self.root, "web", timeout=1):
            with stack_lock(self.root, timeout=1):
                pass

    def test_app_lock_sanitizes_name(self) -> None:
        path = app_lock_path(self.root, "a/b\\c")
        assert path.name == "app-a_b_c.lock"

    def test_close_errors_during_busy_and_release_are_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = stack_lock_path(self.root)
        held = threading.Event()
        release = threading.Event()

        def holder() -> None:
            with exclusive_lock(path, kind="stack", timeout=5):
                held.set()
                release.wait(timeout=5)

        thread = threading.Thread(target=holder)
        thread.start()
        assert held.wait(timeout=2)

        real_close = os.close
        closes = {"n": 0}

        def flaky_close(fd: int) -> None:
            closes["n"] += 1
            if closes["n"] <= 2:
                raise OSError("simulated close failure")
            real_close(fd)

        monkeypatch.setattr(os, "close", flaky_close)
        with pytest.raises(OperatorError, match="holds the stack lock"):
            with exclusive_lock(path, kind="stack", timeout=0.15):
                pass
        release.set()
        thread.join(timeout=2)

        # Successful acquire + release still tolerates close OSError.
        closes["n"] = 0
        with exclusive_lock(path, kind="stack", timeout=1):
            pass
        assert closes["n"] >= 1


class TestUpstreamRaceWithoutLock(RaftTestCase):
    """Prove render can reset another app's mid-cutover upstream (unsafe without flock)."""

    @pytest.fixture(autouse=True)
    def _two_apps(self, _raft_base) -> None:
        write_applied_app(self.tmp_path, "alpha")
        write_applied_app(
            self.tmp_path,
            "beta",
            public_host="beta.test",
        )
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

        # Simulate another app's sync→render (no stack lock held across cutover).
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

        def cutover_holder() -> None:
            with stack_lock(self.stack.root, timeout=5):
                nginx.point_at(
                    self.alpha, self.alpha.tmp_alias, port=self.port, reload=False
                )
                saw_tmp.set()
                release_cutover.wait(timeout=5)

        def concurrent_render() -> None:
            assert saw_tmp.wait(timeout=2)
            with stack_lock(self.stack.root, timeout=5):
                StackRenderer(self.stack).render()
            done_render.set()

        t1 = threading.Thread(target=cutover_holder)
        t2 = threading.Thread(target=concurrent_render)
        t1.start()
        t2.start()
        assert saw_tmp.wait(timeout=2)
        # While cutover holds the lock, upstream must still point at tmp.
        assert self.alpha.tmp_alias in path.read_text(encoding="utf-8")
        assert not done_render.is_set()
        release_cutover.set()
        t1.join(timeout=2)
        t2.join(timeout=2)
        assert done_render.is_set()
        # After cutover releases, render may reset to steady (expected post-cutover).
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
        release_a = threading.Event()

        def deploy_a() -> None:
            with app_and_stack_locks(self.stack.root, "app", timeout=5):
                a_holds.set()
                assert started_b.wait(timeout=2)
                time.sleep(0.05)
                self.live.append("image-A-old")
                release_a.set()

        def deploy_b() -> None:
            assert a_holds.wait(timeout=2)
            started_b.set()
            with app_and_stack_locks(self.stack.root, "app", timeout=5):
                self.live.append("image-B-new")

        t_a = threading.Thread(target=deploy_a)
        t_b = threading.Thread(target=deploy_b)
        t_a.start()
        t_b.start()
        t_a.join(timeout=3)
        t_b.join(timeout=3)
        assert self.live == ["image-A-old", "image-B-new"]

    def test_overlapping_without_lock_last_finisher_can_be_stale(self) -> None:
        """Document the race locks prevent: slow A finishes after B → stale live."""
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

        t_a = threading.Thread(target=slow_old)
        t_b = threading.Thread(target=fast_new)
        t_a.start()
        t_b.start()
        t_a.join(timeout=2)
        t_b.join(timeout=2)
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

        def holder() -> None:
            with stack_lock(self.stack.root, timeout=5):
                held.set()
                release.wait(timeout=5)

        def renderer() -> None:
            try:
                assert held.wait(timeout=2)
                with patch.dict(os.environ, {ENV_LOCK_TIMEOUT: "0.2"}):
                    self.orch.render()
            except BaseException as exc:  # noqa: BLE001 — collect for assert
                errors.append(exc)

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=renderer)
        t1.start()
        t2.start()
        t2.join(timeout=3)
        release.set()
        t1.join(timeout=2)
        assert errors
        assert "holds the stack lock" in str(errors[0])
