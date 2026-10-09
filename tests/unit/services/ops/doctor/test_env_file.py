"""Doctor envFile presence + permission warnings."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from raft.config.app_secrets import AppSecretsLayout
from raft.services.ops.doctor.checks.env_file import EnvFileChecks

from ....base import make_app, make_stack, write_applied_app
from .base import DoctorTestCase


class TestDoctorEnvFile(DoctorTestCase):
    def test_skips_when_no_env_file(self) -> None:
        self._seed_base("site")
        write_applied_app(self.tmp_path, "site")
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_app("site"),)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        assert ("site", "env_file") not in results

    def test_warns_when_missing(self) -> None:
        self._seed_base("demo-api")
        write_applied_app(
            self.tmp_path,
            "demo-api",
            extra={"envFile": "secrets/demo-api/env"},
        )
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_app("demo-api"),)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        row = results[("demo-api", "env_file")]
        assert row.status == "warn"
        assert "missing" in row.detail
        assert "0600" in row.fix

    def test_warns_when_world_readable(self) -> None:
        env = self._write_env(mode=0o644)
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_app("demo-api"),)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        row = results[("demo-api", "env_file")]
        assert row.status == "warn"
        assert "group/world-readable" in row.detail
        assert env.name in row.detail

    def test_ok_when_owner_only(self) -> None:
        self._write_env(mode=0o600)
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_app("demo-api"),)),
            shell=self.mock_shell(),
            docker=self.mock_docker(),
            auth=MagicMock(),
        )
        row = results[("demo-api", "env_file")]
        assert row.status == "ok"
        assert "0600" in row.detail

    def test_loose_path_missing_is_none(self) -> None:
        assert EnvFileChecks._loose_path(self.tmp_path / "nope.env") is None

    def _seed_base(self, *names: str) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        self.write_certs(*names)
        self.ensure_checkouts(*names)

    def _write_env(self, *, mode: int) -> Path:
        self._seed_base("demo-api")
        layout = AppSecretsLayout(self.tmp_path)
        layout.ensure_app_dir("demo-api")
        path = layout.env_file("demo-api")
        path.write_text("DEMO=1\n", encoding="utf-8")
        os.chmod(path, mode)
        write_applied_app(
            self.tmp_path,
            "demo-api",
            extra={"envFile": str(path)},
        )
        return path
