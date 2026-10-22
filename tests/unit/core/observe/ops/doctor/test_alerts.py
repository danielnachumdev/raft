"""Doctor alerts stale / document-error warnings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

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
    def test_skips_when_no_rules(self) -> None:
        self._seed_home()
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

    def _run(self):
        return self.run_keyed(
            StackMakers.make_stack(self.tmp_path, ()),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )

    def _seed_home(self) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        host = self.tmp_path / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text(
            "alerts:\n  enabled: true\n", encoding="utf-8"
        )

    def _write_rules(self) -> None:
        alerts = self.tmp_path / "host" / "alerts"
        alerts.mkdir(parents=True, exist_ok=True)
        (alerts / "rules.yaml").write_text(_RULE, encoding="utf-8")

    def _write_runtime(self, *, finished_at: datetime) -> None:
        alerts = self.tmp_path / "host" / "alerts"
        alerts.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "lastEvaluation": {"finishedAt": finished_at.isoformat()},
            "instances": {},
        }
        (alerts / "runtime.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
