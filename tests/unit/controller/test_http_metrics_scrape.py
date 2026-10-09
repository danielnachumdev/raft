"""Unit tests for GateHttpScraper (access log + stub_status)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

from raft.controller.http_metrics_scrape import GateHttpScraper
from raft.models.app import App
from raft.models.registry import AppRegistry
from raft.models.stack import Stack

from .base import ControllerTestCase

_STUB = "Active connections: 12\nReading: 0 Writing: 4 Waiting: 8\n"


class TestGateHttpScraper(ControllerTestCase):
    def test_sample_reads_new_lines_and_stub(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        self._write_log(home, "0.01 200 demo.test\n0.02 404 demo.test\n")
        scraper = self._scraper(home, stub=_STUB, hosts={"demo.test": "demo-api"})
        first = scraper.sample()
        assert first["requests"] == 2 and first["in_flight"] == 4
        assert first["by_service"]["demo-api"]["status_class"]["4xx"] == 1
        assert scraper.sample()["requests"] == 0

    def test_offset_resets_when_log_shrinks(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        self._write_log(home, "0.01 200 a.test\n")
        scraper = self._scraper(home)
        assert scraper.sample()["requests"] == 1
        self._write_log(home, "0.03 200 b\n")
        assert scraper.sample()["requests"] == 1

    def test_parse_stub_status(self) -> None:
        writing, active = GateHttpScraper.parse_stub_status(
            "Active connections: 9\nReading: 1 Writing: 2 Waiting: 6\n"
        )
        assert writing == 2 and active == 9

    def test_host_map_for_apps_public_host(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        app = App(name="demo-api", public_host="Demo-API.test", source="local", path="a")
        mapping: Dict[str, str] = GateHttpScraper.host_map_for_apps(
            (app,), Stack(root=home, apps=(app,))
        )
        assert mapping["demo-api.test"] == "demo-api"

    def test_stub_status_failure_is_soft(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        scraper = self._scraper(home, fetch=lambda _u: (_ for _ in ()).throw(OSError("x")))
        sample = scraper.sample()
        assert sample["in_flight"] is None and sample["requests"] == 0

    def test_parse_stub_status_bad_lines(self) -> None:
        writing, active = GateHttpScraper.parse_stub_status(
            "Active connections:\njunk\nReading: x Writing: nope Waiting: z\n"
        )
        assert writing is None and active is None
        assert GateHttpScraper._trailing_int("no-colon") is None
        assert GateHttpScraper._field_int("Reading: 1", "writing:") is None
        assert GateHttpScraper._field_int("Writing:", "writing:") is None

    def test_default_host_map_loads_stack(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        AppRegistry(home).write(self._demo_doc())
        scraper = GateHttpScraper(
            home, interval_seconds=1.0, fetch_text=lambda _u: _STUB
        )
        mapping = scraper._default_host_map()
        assert mapping["demo-api.test"] == "demo-api"
        assert mapping["www.demo-api.test"] == "demo-api"

    def test_extra_hosts_soft_fail(self) -> None:
        app = App(name="demo-api", public_host="demo-api.test", source="local", path="a")
        stack = MagicMock(spec=Stack)
        stack.spec_for.side_effect = RuntimeError("bad registry")
        assert GateHttpScraper.host_map_for_apps((app,), stack) == {
            "demo-api.test": "demo-api"
        }

    def test_empty_public_host_uses_extra_hosts_only(self) -> None:
        app = App(name="worker", public_host="", source="local", path="a")
        stack = MagicMock(spec=Stack)
        stack.spec_for.return_value.extra_hosts = ("alias.test",)
        assert GateHttpScraper.host_map_for_apps((app,), stack) == {
            "alias.test": "worker"
        }

    def test_http_get_reads_body(self, monkeypatch) -> None:
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"Active connections: 1\n"

        monkeypatch.setattr(
            "raft.controller.http_metrics_scrape.urllib.request.urlopen",
            lambda *a, **k: _Resp(),
        )
        assert "Active" in GateHttpScraper._http_get("http://example.invalid/")

    @staticmethod
    def _write_log(home: Path, text: str) -> None:
        path = home / "state" / "metrics" / "gate-http" / "access.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def _scraper(home: Path, *, stub: str = _STUB, hosts=None, fetch=None):
        return GateHttpScraper(
            home,
            interval_seconds=1.0,
            fetch_text=fetch or (lambda _url: stub),
            host_map_fn=lambda: hosts or {},
        )

    @staticmethod
    def _demo_doc() -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "demo-api"},
            "spec": {
                "publicHost": "demo-api.test",
                "source": "local",
                "path": "apps/demo-api",
                "extraHosts": ["www.demo-api.test"],
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }
