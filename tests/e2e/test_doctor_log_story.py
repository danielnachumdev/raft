"""E2E story: doctor run writes correlated observability into raft.log."""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest

from raft.config import load_config, reset_logging_for_tests, setup_logging
from raft.config.trace_context import TraceContext
from raft.models.stack import load_stack
from raft.services.ops.doctor import Doctor
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.yaml_doc import YamlDoc

pytestmark = pytest.mark.e2e

_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


class TestDoctorLogObservability:
    """Operator-facing doctor log story (rotation + tid + suite timings).

    Scenario:
      1) raft.log is oversized under configured retentionMaxBytes.
      2) Operator bootstraps logging (CLI setup_logging path) → seal aside.
      3) Operator runs ``raft doctor`` under one TraceContext.
      4) raft.log shows one tid on suite timings and compose-call summary.
    """

    def test_seal_then_doctor_writes_tid_and_suite_timings(
        self, isolated_raft_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = isolated_raft_env
        RaftHomeFixtures.apply_and_render(home, RaftHomeFixtures.fixture_app_yamls("http_only"))
        log_file = self._seed_oversized_log(home, monkeypatch)
        reset_logging_for_tests()
        setup_logging(home, load_config(home))
        assert "ancient-noise" not in log_file.read_text(encoding="utf-8")
        with TraceContext() as tid:
            Doctor(load_stack(home)).report(out=StringIO(), color=False)
        self._assert_observability(log_file.read_text(encoding="utf-8"), tid)

    def _seed_oversized_log(self, home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        YamlDoc(home / "settings.yaml").merge_root(
            "logging",
            {
                "level": "INFO",
                "retentionMaxAgeDays": 30,
                "retentionMaxBytes": 120,
            },
        )
        log_dir = home / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "raft.log"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write_text(
            f"{stamp} INFO - [raft] ancient-noise-aaaaaaaaaaaaaaaa\n"
            f"{stamp} INFO - [raft] keep-line-bbbbbbbbbbbbbbbbbb\n",
            encoding="utf-8",
        )
        return log_file

    def _assert_observability(self, text: str, tid: str) -> None:
        assert tid in text
        assert "doctor suite start name=" in text
        assert "doctor suite done name=" in text and "elapsed_ms=" in text
        assert "doctor compose calls total=" in text and " ps=" in text
        tid_lines = [ln for ln in text.splitlines() if tid in ln and "doctor" in ln]
        assert tid_lines, "expected doctor lines scoped to the invocation tid"
        assert all(_UUID.search(ln) for ln in tid_lines)
