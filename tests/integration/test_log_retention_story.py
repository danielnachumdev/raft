"""Integration story: settings retention knobs prune raft.log on setup_logging."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from raft.config import load_config, reset_logging_for_tests, setup_logging
from tests.shared.raft_home import RaftHomeFixtures
from tests.shared.yaml_doc import YamlDoc

pytestmark = pytest.mark.integration


class TestLogRetentionFromSettings:
    """Operator configures retention in settings.yaml; next CLI start prunes.

    Scenario:
      1) settings.yaml sets a small retentionMaxBytes.
      2) raft.log already holds more than that.
      3) setup_logging (CLI bootstrap) drops oldest lines first.
    """

    def test_settings_retention_prunes_on_cli_logging_setup(
        self, isolated_raft_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = isolated_raft_env
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        RaftHomeFixtures.prepare(home)
        YamlDoc(home / "settings.yaml").merge_root(
            "logging",
            {
                "level": "INFO",
                "retentionMaxAgeDays": 30,
                "retentionMaxBytes": 80,
            },
        )
        log_file = self._write_oversized(home)
        reset_logging_for_tests()
        setup_logging(home, load_config(home))
        text = log_file.read_text(encoding="utf-8")
        assert "old-noise" not in text
        assert "newer-keep" in text
        assert log_file.stat().st_size <= 80

    def _write_oversized(self, home: Path) -> Path:
        log_dir = home / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "raft.log"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write_text(
            f"{stamp} INFO - [raft] old-noise-xxxxxxxxxxxxxxxxxxxx\n"
            f"{stamp} INFO - [raft] newer-keep-yyyyyyyyyyyyyyyy\n",
            encoding="utf-8",
        )
        return log_file
