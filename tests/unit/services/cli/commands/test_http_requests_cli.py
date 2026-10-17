"""CLI ``raft http_requests`` (eligible / ineligible / json)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.read.http_requests import HttpRequestsRead
from raft.services.cli.commands.http_requests import HttpRequestsCLI
from raft.services.controller.jobs.metrics.http_scrape import (
    ACCESS_LOG_NAME,
    GATE_HTTP_LOG_DIR,
)
from tests.unit.base import AppliedInventory, RaftTestCase


class TestHttpRequestsCLI(RaftTestCase):
    def _cli(self) -> HttpRequestsCLI:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        stack = Stack.load_apps(self.tmp_path)
        return HttpRequestsCLI(stack, reader=HttpRequestsRead(stack))

    def _write_log(self, body: str) -> None:
        path = Path(self.tmp_path) / GATE_HTTP_LOG_DIR / ACCESS_LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def _quiet(self):
        return patch("raft.services.cli.commands.http_requests.OperatorSay.say")

    def test_show_eligible_rows(self) -> None:
        cli = self._cli()
        self._write_log(
            '0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /health '
            '192.0.2.10 "DemoAgent/1.0"\n'
        )
        with self._quiet() as say:
            cli.show("demo-api", limit=50)
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "/health" in dumped
        assert "192.0.2.10" in dumped
        assert "apply_inspection" in dumped

    def test_show_json_and_empty(self) -> None:
        cli = self._cli()
        with self._quiet() as say:
            cli.show("demo-api", json=True)
            cli.show("demo-api")
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "eligible" in dumped
        assert "No recent HTTP requests" in dumped

    def test_show_ineligible_gate(self) -> None:
        cli = self._cli()
        with self._quiet() as say:
            cli.show("gate")
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "unavailable" in dumped

    def test_show_unknown_raises(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError, match="not found"):
            cli.show("no-such")

    def test_show_scaled_to_zero_note(self) -> None:
        from raft.core.core.models.state.scaling_store import ScalingStore

        cli = self._cli()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("demo-api")
        with self._quiet() as say:
            cli.show("demo-api")
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "scaled to zero" in dumped

    def test_short_ua_truncates(self) -> None:
        from raft.services.cli.commands.http_requests import _short_ua

        assert _short_ua("short") == "short"
        assert _short_ua("x" * 50).endswith("…")
