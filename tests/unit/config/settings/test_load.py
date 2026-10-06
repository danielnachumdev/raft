"""settings.yaml load coverage."""

from __future__ import annotations

import pytest

from raft.config import LoggingConfig, default_config, load_config

from ...base import RaftTestCase

HEALING_OK_YAML = """
logging:
  level: INFO
  retentionMaxAgeDays: 7
  retentionMaxBytes: 65536
healing:
  enabled: true
  intervalSeconds: 10
  timeoutSeconds: 90
  failThreshold: 2
  cooldownSeconds: 30
  maxRestarts: 4
  escalateAfterRestarts: 3
metrics:
  intervalSeconds: 45
  timeoutSeconds: 20
  batchSize: 5
  flushSeconds: 30
  retentionMaxAgeDays: 14
  retentionMaxBytes: 1048576
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
    ("healing:\n  timeoutSeconds: 0\n", "timeoutSeconds"),
    ("metrics: []\n", "metrics must be a mapping"),
    ("metrics:\n  intervalSeconds: abc\n", "intervalSeconds"),
    ("metrics:\n  batchSize: 0\n", "batchSize"),
    ("metrics:\n  flushSeconds: -1\n", "flushSeconds"),
    ("metrics:\n  retentionMaxAgeDays: 0\n", "retentionMaxAgeDays"),
    ("metrics:\n  retentionMaxBytes: abc\n", "retentionMaxBytes"),
    ("logging:\n  retentionMaxAgeDays: 0\n", "retentionMaxAgeDays"),
    ("logging:\n  retentionMaxBytes: abc\n", "retentionMaxBytes"),
    ("acme: []\n", "acme must be a mapping"),
    ("acme:\n  challenge: dns-01\n", "acme.challenge"),
    ("acme:\n  directory: ''\n", "acme.directory"),
    ("acme:\n  renewDaysBeforeExpiry: 0\n", "renewDaysBeforeExpiry"),
]


class TestConfig(RaftTestCase):
    def test_default_config(self) -> None:
        cfg = default_config()
        assert cfg.logging.dir == "logs"
        assert cfg.logging.file == "raft.log"
        assert cfg.logging.level == "INFO"
        assert cfg.logging.retention_max_age_days == 30
        assert cfg.logging.retention_max_bytes == 100 * 1024 * 1024
        assert cfg.healing.enabled is False
        assert cfg.healing.fail_threshold == 3
        assert cfg.healing.max_restarts == 1
        assert cfg.healing.escalate_after_restarts == 1
        assert cfg.healing.timeout_seconds == 120.0
        assert cfg.metrics.interval_seconds == 60.0
        assert cfg.metrics.timeout_seconds == 30.0
        assert cfg.metrics.batch_size == 10
        assert cfg.metrics.flush_seconds == 60.0
        assert cfg.metrics.retention_max_age_days == 30
        assert cfg.metrics.retention_max_bytes == 100 * 1024 * 1024
        self._assert_acme_defaults(cfg)

    def _assert_acme_defaults(self, cfg) -> None:
        assert cfg.acme.email is None
        assert cfg.acme.directory.startswith("https://acme-v02.api.letsencrypt.org")
        assert cfg.acme.renew_days_before_expiry == 30
        assert cfg.acme.challenge == "http-01"

    def test_load_acme_section(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "acme:\n"
            "  email: ops@example.com\n"
            "  directory: https://acme-staging-v02.api.letsencrypt.org/directory\n"
            "  renewDaysBeforeExpiry: 14\n"
            "  challenge: http-01\n",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.acme.email == "ops@example.com"
        assert "staging" in cfg.acme.directory
        assert cfg.acme.renew_days_before_expiry == 14
        assert cfg.acme.challenge == "http-01"

    def test_load_acme_defaults_challenge_when_omitted(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "acme:\n  email: ops@example.com\n",
            encoding="utf-8",
        )
        cfg = load_config(self.tmp_path)
        assert cfg.acme.email == "ops@example.com"
        assert cfg.acme.challenge == "http-01"
        assert cfg.acme.directory.startswith("https://acme-v02")

    def test_load_healing_section(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(HEALING_OK_YAML, encoding="utf-8")
        cfg = load_config(self.tmp_path)
        assert cfg.healing.enabled is True
        assert cfg.healing.interval_seconds == 10
        assert cfg.healing.timeout_seconds == 90
        assert cfg.healing.fail_threshold == 2
        assert cfg.healing.cooldown_seconds == 30
        assert cfg.healing.max_restarts == 4
        assert cfg.healing.escalate_after_restarts == 3
        assert cfg.logging.retention_max_age_days == 7
        assert cfg.logging.retention_max_bytes == 65536
        assert cfg.metrics.interval_seconds == 45
        assert cfg.metrics.timeout_seconds == 20
        assert cfg.metrics.batch_size == 5
        assert cfg.metrics.flush_seconds == 30
        assert cfg.metrics.retention_max_age_days == 14
        assert cfg.metrics.retention_max_bytes == 1048576

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
