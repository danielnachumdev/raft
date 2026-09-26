"""Apply env expansion coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml

from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.apply.manifest_env import ApplyEnvSources
from raft.services.render import StackRenderer

from ..fixtures import (
    CI_TO_CONTAINER_APPLY_ENV,
    CI_TO_CONTAINER_ENV_MANIFEST,
    CI_TO_CONTAINER_FLAG_OVERRIDES,
    MISSING_VAR_FILE_MANIFEST,
    PLACEHOLDER_FILE_MANIFEST,
    clone_writes_missing_var_manifest,
    clone_writes_placeholder_manifest,
)
from .base import ApplyTestCase


class TestApplyEnv(ApplyTestCase):
    def test_apply_file_expands_env_into_registry_before_parse(self) -> None:
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(PLACEHOLDER_FILE_MANIFEST, encoding="utf-8")
        env_file = self.tmp_path / "apply.env"
        env_file.write_text("RAFT_APP_NAME=from-file\n", encoding="utf-8")
        apply_env = ApplyEnvSources(
            environ={"RAFT_APP_NAME": "from-process"},
            env_file=env_file,
            overrides=["RAFT_APP_NAME=expanded-web"],
        ).build()
        applied = AppApply(load_stack(self.tmp_path)).apply_file(
            manifest, deploy=False, env=apply_env
        )
        self._assert_expanded_registry(applied)

    def _assert_expanded_registry(self, applied_name: str) -> None:
        registry_path = self.tmp_path / "state" / "apps" / f"{applied_name}.yaml"
        registry_text = registry_path.read_text(encoding="utf-8")
        registry = yaml.safe_load(registry_text)
        assert applied_name == "expanded-web"
        assert registry["metadata"]["name"] == "expanded-web"
        assert registry["spec"]["publicHost"] == "web.test"
        assert registry["spec"]["path"] == "apps/expanded-web"
        assert "${" not in registry_text

    def test_apply_file_missing_var_fails(self) -> None:
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(MISSING_VAR_FILE_MANIFEST, encoding="utf-8")
        with pytest.raises(RuntimeError, match="undefined variable MISSING") as caught:
            AppApply(load_stack(self.tmp_path)).apply_file(manifest, deploy=False, env={})
        assert "MISSING" in str(caught.value)

    def test_apply_expands_ci_env_into_container_spec_then_compose(self) -> None:
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(CI_TO_CONTAINER_ENV_MANIFEST, encoding="utf-8")
        apply_env = ApplyEnvSources(
            environ=CI_TO_CONTAINER_APPLY_ENV, overrides=CI_TO_CONTAINER_FLAG_OVERRIDES
        ).build()
        applied = AppApply(load_stack(self.tmp_path)).apply_file(
            manifest, deploy=False, env=apply_env
        )
        self._assert_ci_registry(applied)
        self._assert_ci_compose()

    def _assert_ci_registry(self, applied_name: str) -> None:
        registry = yaml.safe_load(
            (self.tmp_path / "state" / "apps" / f"{applied_name}.yaml").read_text(
                encoding="utf-8"
            )
        )
        env = registry["spec"]["env"]
        assert applied_name == "api-dev"
        assert registry["spec"]["envFile"] == "/home/raft/.raft/api-dev.env"
        assert env["DATABASE_URL"] == "postgres://from-ci-flag"
        assert env["LOG_LEVEL"] == "info"
        assert "${" not in yaml.safe_dump(registry)

    def _assert_ci_compose(self) -> None:
        StackRenderer(load_stack(self.tmp_path)).render()
        compose = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(
            encoding="utf-8"
        )
        assert "environment:" in compose
        assert 'DATABASE_URL: "postgres://from-ci-flag"' in compose
        assert "LOG_LEVEL: info" in compose
        assert "env_file:" in compose
        assert "/home/raft/.raft/api-dev.env" in compose

    def test_apply_git_expands_env_into_registry(self) -> None:
        shell = MagicMock()
        shell.git.side_effect = clone_writes_placeholder_manifest
        applied = self.applier(load_stack(self.tmp_path), shell).apply_git(
            "git@github.com:org/x.git", deploy=False, env={"APP_NAME": "from-git"}
        )
        registry = yaml.safe_load(
            (self.tmp_path / "state" / "apps" / f"{applied}.yaml").read_text(encoding="utf-8")
        )
        assert applied == "from-git"
        assert registry["metadata"]["name"] == "from-git"
        assert registry["spec"]["path"] == "apps/from-git"

    def test_apply_git_missing_var_fails(self) -> None:
        shell = MagicMock()
        shell.git.side_effect = clone_writes_missing_var_manifest
        with pytest.raises(RuntimeError, match="undefined variable MISSING") as caught:
            self.applier(load_stack(self.tmp_path), shell).apply_git(
                "git@github.com:org/x.git", deploy=False, env={}
            )
        assert "MISSING" in str(caught.value)
