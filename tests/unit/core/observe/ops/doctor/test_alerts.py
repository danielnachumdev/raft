"""Doctor alerts stale / document-error warnings."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.ops.doctor.checks.alerts import AlertsChecks
from raft.core.observe.ops.doctor.models import INFRA
from tests.unit.base import StackMakers
from tests.unit.core.observe.ops.doctor.base import DoctorTestCase

_RULE = """\
version: 1
rules:
  - id: demo-api-5xx-rate
    name: demo
    severity: error
    for: 0s
    cooldown: 15m
    condition:
      signal: metrics.http
      select: {target: demo-api, metric: error_rate_5xx}
      kind: threshold
      params: {aggregate: avg, window: 5m, op: gt, value: 0.05}
"""


class TestDoctorAlerts(DoctorTestCase):
    def test_skips_when_disabled(self) -> None:
        self._seed_home(enabled=False)
        self._write_rules()
        assert (INFRA, "alerts") not in self._run()

    def test_skips_when_no_rules(self) -> None:
        self._seed_home(enabled=True)
        assert (INFRA, "alerts") not in self._run()

    def test_warns_when_stale(self) -> None:
        self._seed_home()
        self._write_rules()
        row = self._run()[(INFRA, "alerts")]
        assert row.status == "warn"
        assert "not evaluated" in row.detail
        assert "raft up" in row.fix

    def test_ok_when_fresh(self) -> None:
        self._seed_home()
        self._write_rules()
        self._write_runtime(finished_at=datetime.now(timezone.utc))
        assert self._run()[(INFRA, "alerts")].status == "ok"

    def test_document_error_and_bad_shapes(self) -> None:
        self._seed_home()
        self._write_text("rules.yaml", "[]\n")
        row = self._run()[(INFRA, "alerts")]
        assert row.status == "warn" and "document error" in row.detail
        self._assert_rules_info_edges()

    def test_runtime_and_stale_edges(self) -> None:
        self._assert_last_evaluation_edges()
        self._assert_is_stale_edges()

    def _assert_rules_info_edges(self) -> None:
        checks = AlertsChecks()
        assert checks._rules_info(self.tmp_path / "missing.yaml") == (0, None)
        empty = self.tmp_path / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        assert checks._rules_info(empty) == (0, None)
        bad_rules = self.tmp_path / "bad-rules.yaml"
        bad_rules.write_text("rules: not-a-list\n", encoding="utf-8")
        assert checks._rules_info(bad_rules)[1] == "rules must be a list"
        broken = self.tmp_path / "broken.yaml"
        broken.write_text(": [\n", encoding="utf-8")
        assert checks._rules_info(broken)[1] is not None
        with patch.object(Path, "read_text", side_effect=OSError("boom")):
            assert checks._rules_info(broken)[1] == "boom"

    def _assert_last_evaluation_edges(self) -> None:
        checks = AlertsChecks()
        assert checks._last_evaluation(self.tmp_path / "nope.json") is None
        path = self.tmp_path / "runtime.json"
        path.write_text("not-json", encoding="utf-8")
        assert checks._last_evaluation(path) is None
        path.write_text("[]", encoding="utf-8")
        assert checks._last_evaluation(path) is None
        path.write_text('{"lastEvaluation": "x"}', encoding="utf-8")
        assert checks._last_evaluation(path) is None
        with patch.object(Path, "read_text", side_effect=OSError("boom")):
            assert checks._last_evaluation(path) is None

    def _assert_is_stale_edges(self) -> None:
        checks = AlertsChecks()
        assert checks._is_stale(None, 60) is True
        assert checks._is_stale({"finishedAt": "nope"}, 60) is True
        assert checks._is_stale({"finishedAt": object()}, 60) is True
        naive = datetime.now().replace(tzinfo=None).isoformat()
        assert checks._is_stale({"finishedAt": naive}, 60) is False
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert checks._is_stale({"finishedAt": old}, 60) is True

    def _run(self):
        return self.run_keyed(
            StackMakers.make_stack(self.tmp_path, ()),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )

    def _seed_home(self, *, enabled: bool = True) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        flag = "true" if enabled else "false"
        (host / "settings.yaml").write_text(
            f"alerts:\n  enabled: {flag}\n", encoding="utf-8"
        )

    def _write_rules(self) -> None:
        self._write_text("rules.yaml", _RULE)

    def _write_runtime(self, *, finished_at: datetime) -> None:
        payload = {
            "version": 1,
            "lastEvaluation": {"finishedAt": finished_at.isoformat()},
            "instances": {},
        }
        self._write_text("runtime.json", json.dumps(payload))

    def _write_text(self, name: str, body: str) -> Path:
        alerts = self.tmp_path / "host" / "alerts"
        alerts.mkdir(parents=True, exist_ok=True)
        path = alerts / name
        path.write_text(body, encoding="utf-8")
        return path
