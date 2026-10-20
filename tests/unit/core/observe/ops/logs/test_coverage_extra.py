"""Extra branch coverage for service-logs store / capture / hooks / keys."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.observe.ops.logs.capture import ServiceLogsCapture
from raft.core.observe.ops.logs.hooks import ServiceLogsHooks
from raft.core.observe.ops.logs.keys import ServiceLogsKeys
from raft.core.observe.ops.logs.meta import ServiceLogsMeta, ServiceLogsMetaStore
from raft.core.observe.ops.logs.reader import ServiceLogsReader
from raft.core.observe.ops.logs.store import ServiceLogsStore

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class _BoomSource:
    def fetch(self, container: str, *, since: str) -> str:
        raise RuntimeError("docker gone")


class _SeqSource:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)

    def fetch(self, container: str, *, since: str) -> str:
        return self.texts.pop(0) if self.texts else ""


class TestServiceLogsCoverage(RaftTestCase):
    def test_capture_fetch_error_returns_zero(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        assert ServiceLogsCapture(store, _BoomSource()).ship("demo-api", "cid") == 0

    def test_capture_skips_blank_and_untimestamped_with_cursor(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        store.save_meta(
            "demo-api",
            ServiceLogsMeta(container_id="cid", cursor="2026-10-14T12:00:00Z"),
        )
        source = _SeqSource(
            ["\nnotimestamp\n2026-10-14T12:00:01Z ok\n"]
        )
        n = ServiceLogsCapture(store, source).ship("demo-api", "cid")
        assert n == 1
        assert "ok" in store.active_path("demo-api").read_text(encoding="utf-8")

    def test_capture_keeps_untimestamped_without_cursor(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        source = _SeqSource(["raw-line\n"])
        assert ServiceLogsCapture(store, source).ship("demo-api", "cid") == 1
        assert "raw-line" in store.active_path("demo-api").read_text(encoding="utf-8")

    def test_store_append_empty_noop(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        store.append_lines("demo-api", [])
        assert not store.active_path("demo-api").exists()

    def test_store_append_oserror(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        active = store.active_path("demo-api")
        active.parent.mkdir(parents=True, exist_ok=True)
        # Directory where a file is required → OSError on open("a").
        active.mkdir()
        with pytest.raises(OSError):
            store.append_lines("demo-api", ["x"])

    def test_meta_corrupt_and_non_dict(self) -> None:
        path = self.tmp_path / "svc"
        path.mkdir()
        meta_path = path / "meta.json"
        meta_path.write_text("{bad", encoding="utf-8")
        assert ServiceLogsMetaStore(path).load().cursor == ""
        meta_path.write_text("[]", encoding="utf-8")
        assert ServiceLogsMetaStore(path).load().cursor == ""

    def test_meta_save_oserror_swallowed(self) -> None:
        store = ServiceLogsMetaStore(self.tmp_path / "svc")
        with patch.object(Path, "write_text", side_effect=OSError("nope")):
            store.save(ServiceLogsMeta(container_id="x"))

    def test_reader_skips_unreadable_and_meta(self) -> None:
        store = ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
        active = store.active_path("demo-api")
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text("visible\n", encoding="utf-8")
        (active.parent / "meta.json").write_text("{}", encoding="utf-8")
        (active.parent / "noise.txt").write_text("x\n", encoding="utf-8")
        sealed = active.parent / "current.log.2026-10-13"
        sealed.write_text("old\n", encoding="utf-8")
        sealed.chmod(0o000)
        try:
            text = ServiceLogsReader(store).tail("demo-api", lines=5)
        finally:
            sealed.chmod(0o600)
        assert "visible" in text

    def test_keys_app_and_compose(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        keys = ServiceLogsKeys(stack)
        assert keys.key_for_compose_id("demo-api") == "demo-api"
        assert keys.key_for_container_name("demo-api") == "demo-api"
        assert keys.key_for_container_name(stack.apps[0].tmp_alias) == "demo-api"
        assert keys.key_for_container_name(stack.apps[0].tmp_container) == "demo-api"

    def test_keys_tmp_patterns_and_unknown(self) -> None:
        keys = ServiceLogsKeys(StackMakers.make_stack(self.tmp_path, ()))
        assert keys.key_for_container_name("foreign_tmp") == "foreign"
        assert keys.key_for_container_name("raft-_tmp") is None
        assert keys.key_for_container_name("") is None
        assert keys.key_for_container_name("unknown-box") is None
        assert keys.key_for_container_name("_tmp") is None

    def test_hooks_stack_down_and_missing_container(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        docker = MagicMock()
        docker.try_service_container_id.return_value = None
        cfg = MagicMock(
            enabled=True, retention_max_age_days=14, retention_max_bytes=1024,
            include_edge=False,
        )
        with patch.object(ServiceLogsHooks, "_config", return_value=cfg):
            ServiceLogsHooks.before_stack_down(stack, docker)
            ServiceLogsHooks.before_compose_recreate(stack, "demo-api", docker)
            ServiceLogsHooks.before_compose_recreate(stack, "", docker)
            ServiceLogsHooks.before_container_remove(stack, "", docker)

    def test_hooks_named_unknown_uses_name_as_key(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        source = MagicMock()
        source.fetch.return_value = "2026-10-14T12:00:00.000000000Z orphan\n"
        cfg = MagicMock(
            enabled=True, retention_max_age_days=14, retention_max_bytes=1024,
            include_edge=True,
        )
        with patch.object(ServiceLogsHooks, "_config", return_value=cfg):
            with patch(
                "raft.core.observe.ops.logs.hooks.DockerContainerLogSource",
                return_value=source,
            ):
                ServiceLogsHooks.before_container_remove(
                    stack, "orphan-cid", MagicMock()
                )
        self._assert_file("orphan-cid", "orphan")

    def test_hooks_stack_down_disabled_via_settings(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "serviceLogs:\n  enabled: false\n", encoding="utf-8"
        )
        docker = MagicMock()
        ServiceLogsHooks.before_stack_down(stack, docker)
        docker.try_service_container_id.assert_not_called()

    def test_hooks_builds_docker_when_omitted(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        engine = MagicMock()
        engine.try_service_container_id.return_value = "cid"
        source = MagicMock()
        source.fetch.return_value = "2026-10-14T12:00:00.000000000Z from-built\n"
        cfg = MagicMock(
            enabled=True, retention_max_age_days=14, retention_max_bytes=1024,
            include_edge=True,
        )
        with patch.object(ServiceLogsHooks, "_config", return_value=cfg):
            with patch(
                "raft.core.platform.adapters.docker.stack.DockerStack",
                return_value=engine,
            ):
                with patch(
                    "raft.core.observe.ops.logs.hooks.DockerContainerLogSource",
                    return_value=source,
                ):
                    ServiceLogsHooks.before_stack_down(stack, None)
        self._assert_file("raft-gate", "from-built")

    def _assert_file(self, key: str, needle: str) -> None:
        text = (
            ServiceLogsStore(self.tmp_path, max_age_days=14, max_bytes=1024)
            .active_path(key)
            .read_text(encoding="utf-8")
        )
        assert needle in text
