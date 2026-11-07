"""Drain-before-remove hooks capture last Docker lines into the store."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.logs.hooks import ServiceLogsHooks
from raft.core.observe.ops.logs.store import ServiceLogsStore

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


def _enabled_cfg(**overrides) -> MagicMock:
    cfg = MagicMock(
        enabled=True,
        retention_max_age_days=14,
        retention_max_bytes=1024,
        include_edge=True,
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


class TestServiceLogsHooks(RaftTestCase):
    def _patch_source(self, text: str):
        source = MagicMock()
        source.fetch.return_value = text
        return patch(
            "raft.core.observe.ops.logs.hooks.DockerContainerLogSource",
            return_value=source,
        ), source

    def test_before_container_remove_drains_tmp_into_app_store(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        docker = MagicMock()
        src_patch, source = self._patch_source(
            "2026-10-14T12:00:00.000000000Z last-line-before-rm\n"
        )
        with patch.object(ServiceLogsHooks, "_config", return_value=_enabled_cfg()):
            with src_patch:
                ServiceLogsHooks.before_container_remove(
                    stack, "raft-demo-api_tmp", docker
                )
        self._assert_retained("demo-api", "last-line-before-rm")
        source.fetch.assert_called_once()

    def test_before_compose_recreate_drains_running_container(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        docker = MagicMock()
        docker.try_service_container_id.return_value = "cid-live"
        src_patch, _source = self._patch_source(
            "2026-10-14T12:00:00.000000000Z before-recreate\n"
        )
        with patch.object(ServiceLogsHooks, "_config", return_value=_enabled_cfg()):
            with src_patch:
                ServiceLogsHooks.before_compose_recreate(stack, "demo-api", docker)
        self._assert_retained("demo-api", "before-recreate")

    def test_disabled_skips_drain(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        docker = MagicMock()
        with patch.object(
            ServiceLogsHooks, "_config", return_value=MagicMock(enabled=False)
        ):
            ServiceLogsHooks.before_compose_recreate(stack, "raft-gate", docker)
        docker.try_service_container_id.assert_not_called()

    def test_drain_errors_are_swallowed(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        with patch.object(
            ServiceLogsHooks, "_drain_compose", side_effect=RuntimeError("boom")
        ):
            ServiceLogsHooks.before_compose_recreate(stack, "raft-gate", MagicMock())

    def test_stack_down_ships_services_in_parallel(self) -> None:
        """Multi-service drain overlaps IO instead of shipping one-by-one."""
        stack = StackMakers.make_stack(
            self.tmp_path,
            (AppMakers.make_app("demo-api"), AppMakers.make_app("demo-web")),
        )
        docker = MagicMock()
        docker.try_service_container_id.side_effect = lambda sid: f"cid-{sid}"
        gate = threading.Barrier(2, timeout=2)
        capture = MagicMock()
        capture.ship.side_effect = self._slow_ship(gate)
        started = time.monotonic()
        self._stack_down(stack, docker, capture, include_edge=False)
        elapsed = time.monotonic() - started
        assert capture.ship.call_count == 2
        assert elapsed < 0.35

    def test_stack_down_ships_single_service_inline(self) -> None:
        """One target ships on the calling thread (no pool)."""
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        docker = MagicMock()
        docker.try_service_container_id.side_effect = lambda sid: f"cid-{sid}"
        capture = MagicMock()
        self._stack_down(stack, docker, capture, include_edge=False)
        capture.ship.assert_called_once_with("demo-api", "cid-demo-api")

    @staticmethod
    def _stack_down(stack, docker, capture, *, include_edge: bool) -> None:
        with patch.object(
            ServiceLogsHooks, "_config", return_value=_enabled_cfg(include_edge=include_edge)
        ):
            with patch.object(ServiceLogsHooks, "_capture", return_value=capture):
                ServiceLogsHooks.before_stack_down(stack, docker)

    @staticmethod
    def _slow_ship(gate: threading.Barrier):
        def ship(_key: str, _cid: str) -> int:
            gate.wait()
            time.sleep(0.15)
            return 0

        return ship

    def _assert_retained(self, key: str, needle: str) -> None:
        text = (
            ServiceLogsStore(
                self.tmp_path,
                max_age_days=14,
                max_bytes=1024,
                compose_to_app={key: key},
            )
            .active_path(key)
            .read_text(encoding="utf-8")
        )
        assert needle in text
