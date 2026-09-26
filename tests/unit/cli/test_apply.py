"""CLI apply / get / delete coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft import cli

from ..base import make_app, make_stack, write_demo_inventory
from .base import CliTestCase


class TestCliApplyGetDelete(CliTestCase):
    def test_apply_merges_env_file_and_flags_into_single_env_map(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        env_path = self.tmp_path / "vars.env"
        env_path.write_text("FROM_FILE=yes\nA=from-file\n", encoding="utf-8")
        argv = [
            "apply",
            "--file",
            "app.yaml",
            "--no-deploy",
            "--env-file",
            str(env_path),
            "--env",
            "A=1",
            "--env",
            "B=2",
        ]
        with self.patched_deps(stack=stack, AppApply=applier):
            exit_code = cli.main(argv)
        self._assert_merged_env(applier, exit_code)

    def _assert_merged_env(self, applier, exit_code) -> None:
        call_kwargs = applier.apply_file.call_args.kwargs
        apply_env = call_kwargs["env"]
        assert exit_code == 0
        assert "env_file" not in call_kwargs and "env_overrides" not in call_kwargs
        assert apply_env["FROM_FILE"] == "yes"
        assert apply_env["A"] == "1" and apply_env["B"] == "2"

    def test_apply_without_env_flags_still_passes_process_env_map(self) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"),))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        with self.patched_deps(stack=stack, AppApply=applier):
            exit_code = cli.main(["apply", "--file", "app.yaml", "--no-deploy"])
        call_kwargs = applier.apply_file.call_args.kwargs
        assert exit_code == 0 and isinstance(call_kwargs["env"], dict)
        assert "env_file" not in call_kwargs and "env_overrides" not in call_kwargs

    def test_apply_get_delete_dispatch(self, capsys) -> None:
        write_demo_inventory(self.tmp_path)
        stack = make_stack(self.tmp_path, (make_app("app"), make_app("other")))
        applier = MagicMock()
        applier.apply_file.return_value = "web"
        applier.apply_git.return_value = "hub"
        self._assert_apply_dispatch(stack, applier)
        self._assert_get_dispatch(stack, capsys)
        self._assert_delete_dispatch(stack, applier)

    def _assert_apply_dispatch(self, stack, applier) -> None:
        with self.patched_deps(stack=stack, AppApply=applier):
            assert cli.main(["apply", "--file", "app.yaml", "--no-deploy"]) == 0
            applier.apply_file.assert_called_once()
            assert (
                cli.main(
                    [
                        "apply",
                        "--git",
                        "git@github.com:org/hub.git",
                        "--ref",
                        "main",
                        "--force-sync",
                    ]
                )
                == 0
            )
            applier.apply_git.assert_called_once()
            with pytest.raises(RuntimeError, match="apply requires"):
                cli.main(["apply"])

    def _assert_get_dispatch(self, stack, capsys) -> None:
        empty = make_stack(self.tmp_path, ())
        with self.patched_deps(stack=empty):
            assert cli.main(["get", "apps"]) == 0
            assert "No apps applied" in capsys.readouterr().out
        with self.patched_deps(stack=stack):
            assert cli.main(["get", "apps"]) == 0
            assert "app" in capsys.readouterr().out
            assert cli.main(["get", "app", "app"]) == 0
            with pytest.raises(SystemExit):
                cli.main(["get", "app"])
            with pytest.raises(SystemExit):
                cli.main(["get", "nope"])

    def _assert_delete_dispatch(self, stack, applier) -> None:
        with self.patched_deps(stack=stack, AppApply=applier):
            assert cli.main(["delete", "app", "app"]) == 0
            applier.delete.assert_called_once_with("app")
            with pytest.raises(SystemExit):
                cli.main(["delete", "app"])
            with pytest.raises(SystemExit):
                cli.main(["delete", "nope"])
