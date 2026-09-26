"""settings.yaml load coverage."""

from __future__ import annotations

import pytest

from raft.config import LoggingConfig, default_config, load_config

from ...base import RaftTestCase

HEALING_OK_YAML = """
logging:
  level: INFO
healing:
  enabled: true
  intervalSeconds: 10
  failThreshold: 2
  cooldownSeconds: 30
  maxRestarts: 4
  escalateAfterRestarts: 3
edge:
  http: 80
"""

HEALING_ERROR_CASES = [
    ("healing: []\n", "healing must be a mapping"),
    ("healing:\n  failThreshold: 0\n", "failThreshold"),
    ("healing:\n  intervalSeconds: abc\n", "intervalSeconds"),
    ("healing:\n  cooldownSeconds: []\n", "cooldownSeconds"),
    ("healing:\n  cooldownSeconds: 0\n", "cooldownSeconds"),
    ("healing:\n  maxRestarts: x\n", "maxRestarts"),
    ("healing:\n  escalateAfterRestarts: 0\n", "escalateAfterRestarts"),
]


class TestConfig(RaftTestCase):
    def test_default_config(self) -> None:
        cfg = default_config()
        assert cfg.logging.dir == "logs"
        assert cfg.logging.file == "raft.log"
        assert cfg.logging.level == "INFO"
        assert cfg.healing.enabled is False
        assert cfg.healing.fail_threshold == 3
        assert cfg.healing.max_restarts == 1
        assert cfg.healing.escalate_after_restarts == 1

    def test_load_healing_section(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(HEALING_OK_YAML, encoding="utf-8")
        cfg = load_config(self.tmp_path)
        assert cfg.healing.enabled is True
        assert cfg.healing.interval_seconds == 10
        assert cfg.healing.fail_threshold == 2
        assert cfg.healing.cooldown_seconds == 30
        assert cfg.healing.max_restarts == 4
        assert cfg.healing.escalate_after_restarts == 3

    def test_load_healing_invalid(self) -> None:
        for body, match in HEALING_ERROR_CASES:
            (self.tmp_path / "settings.yaml").write_text(body, encoding="utf-8")
            with pytest.raises(RuntimeError, match=match):
                load_config(self.tmp_path)

    def test_load_missing_uses_defaults(self) -> None:
        settings = self.tmp_path / "settings.yaml"
        if settings.is_file():
            settings.unlink()
        assert load_config(self.tmp_path) == default_config()

    def test_load_from_file(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "logging:\n  dir: var/log\n  file: orch.log\n  level: DEBUG\n",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.logging.dir == "var/log"
        assert cfg.logging.file == "orch.log"
        assert cfg.logging.level == "DEBUG"

    def test_rejects_bad_logging_table(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("logging: nope\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="must be a mapping"):
            load_config(self.tmp_path)

    def test_load_logging_null(self) -> None:
        (self.tmp_path / "settings.yaml").write_text("# no logging mapping\n", encoding="utf-8")
        assert load_config(self.tmp_path).logging.dir == "logs"

    def test_resolve_dir_relative_absolute_and_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAFT_LOG_DIR", raising=False)
        cfg = LoggingConfig(dir="logs")
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "logs").resolve()
        abs_cfg = LoggingConfig(dir=str(self.tmp_path / "abs-logs"))
        assert abs_cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "abs-logs").resolve()
        monkeypatch.setenv("RAFT_LOG_DIR", str(self.tmp_path / "env-logs"))
        assert cfg.resolve_dir(self.tmp_path) == (self.tmp_path / "env-logs").resolve()
