"""Apply from git coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.auth import GitAuthManager

from ..base import ServicesTestCase
from ...base import write_applied_app
from .base import ApplyTestCase


class TestApplyGit(ApplyTestCase):
    def test_apply_git_shallow_and_fallback(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        doc = self.manifest(
            "hub", source="docker", public_host="hub.test", image="ghcr.io/org/hub"
        )
        shell.git.side_effect = self.clone_side_effect(doc, strip_build=True)
        assert self.applier(stack, shell).apply_git(
            "git@github.com:org/hub.git", ref="main", deploy=False
        ) == "hub"
        assert shell.git.call_count >= 1
        self._assert_shallow_fallback(stack)

    def _assert_shallow_fallback(self, stack) -> None:
        calls = {"n": 0}

        def fail_shallow_then_ok(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("shallow failed")
            if "clone" not in args:
                return
            doc = self.manifest("gitapp", source="git", repo="git@github.com:org/x.git")
            doc["spec"].pop("image", None)
            self.write_clone_manifest(Path(args[-1]), doc)

        shell2 = MagicMock()
        shell2.git.side_effect = fail_shallow_then_ok
        assert self.applier(stack, shell2).apply_git(
            "git@github.com:org/x.git", ref="dev", deploy=False
        ) == "gitapp"

    def test_apply_git_missing_manifest_and_bad_docs(self) -> None:
        stack = load_stack(self.tmp_path)
        self._raise_on_clone(stack, lambda t: None, match="app.yaml")
        self._raise_on_clone(
            stack, lambda t: self._write_raw(t, "- x\n"), match="mapping"
        )
        self._raise_on_clone(
            stack,
            lambda t: self._write_raw(
                t, "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: z\nspec: []\n"
            ),
            match="spec must be an object",
            exc=ValueError,
        )

    def _write_raw(self, target: Path, text: str) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / ".raft").mkdir(parents=True, exist_ok=True)
        (target / ".raft" / "app.yaml").write_text(text, encoding="utf-8")

    def _raise_on_clone(self, stack, writer, *, match: str, exc=RuntimeError) -> None:
        shell = MagicMock()

        def clone(*args, **kwargs):
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            writer(target)

        shell.git.side_effect = clone
        with pytest.raises(exc, match=match):
            self.applier(stack, shell).apply_git("git@x/y.git", deploy=False)

    def test_apply_git_auth_failure_hints_setup(self) -> None:
        import subprocess

        shell = MagicMock()

        def denied(*args, **kwargs):
            raise subprocess.CalledProcessError(
                128, args, stderr="git@github.com: Permission denied (publickey).\n"
            )

        shell.git.side_effect = denied
        with pytest.raises(RuntimeError, match="auth setup .* --repo"):
            self.applier(load_stack(self.tmp_path), shell).apply_git(
                "git@github.com:Playloft-Studio/playloftstudio.com.git", deploy=False
            )

    def test_apply_git_non_auth_clone_error_reraises(self) -> None:
        shell = MagicMock()
        shell.git.side_effect = RuntimeError("network unreachable")
        with pytest.raises(RuntimeError, match="cannot reach git host"):
            self.applier(load_stack(self.tmp_path), shell).apply_git(
                "git@github.com:org/x.git", deploy=False
            )

    def test_apply_git_bad_manifest_yaml(self) -> None:
        shell = MagicMock()

        def clone(*args, **kwargs):
            self._write_raw(Path(args[-1]), "{{{{")

        shell.git.side_effect = clone
        with pytest.raises(RuntimeError, match="invalid App manifest YAML"):
            self.applier(load_stack(self.tmp_path), shell).apply_git(
                "git@github.com:org/x.git", deploy=False
            )

    def test_apply_git_retries_host_alias(self) -> None:
        stack = load_stack(self.tmp_path)
        shell, mgr, calls = self._alias_shell_and_manager()
        shell.git.side_effect = self._alias_clone(calls)
        with patch("raft.services.apply.GitAuthManager", return_value=mgr):
            name = self.applier(stack, shell).apply_git(
                "git@github.com:Playloft-Studio/playloftstudio.com.git", deploy=False
            )
        assert name == "playloftstudio"
        assert any("raft-playloftstudio" in u for u in calls)

    def _alias_shell_and_manager(self):
        shell = MagicMock()
        auth_dir = self.tmp_path / "ssh-apply"
        mgr = GitAuthManager(load_stack(self.tmp_path))
        mgr.sh = shell
        mgr.ssh_dir = auth_dir
        mgr.keys_dir = auth_dir / "raft"
        mgr.config_path = auth_dir / "config"
        ServicesTestCase.write_keypair(mgr, "playloftstudio")
        return shell, mgr, []

    def _alias_clone(self, calls: list):
        def clone_alias(*args, **kwargs):
            if "clone" not in args:
                return MagicMock(returncode=0)
            url = args[-2]
            calls.append(url)
            if "raft-playloftstudio" not in url:
                raise RuntimeError("Permission denied (publickey)")
            self.write_clone_manifest(
                Path(args[-1]),
                self.manifest(
                    "playloftstudio", source="git",
                    repo="git@github.com:Playloft-Studio/playloftstudio.com.git",
                    public_host="playloftstudio.com",
                ),
            )

        return clone_alias

    def test_delete_re_renders(self, capsys) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test")
        write_applied_app(self.tmp_path, "other", public_host="other.test")
        with patch("raft.services.apply.Orchestrator") as orch_cls:
            AppApply(load_stack(self.tmp_path)).delete("web")
            orch_cls.return_value.render.assert_called_once()
        assert not (self.tmp_path / "state" / "apps" / "web.yaml").is_file()
        assert "deleted web" in capsys.readouterr().out
        self._delete_leftovers_and_ghost(capsys)

    def _delete_leftovers_and_ghost(self, capsys) -> None:
        for leftover in ("other", "app"):
            path = self.tmp_path / "state" / "apps" / f"{leftover}.yaml"
            if path.is_file():
                with patch("raft.services.apply.Orchestrator") as orch_cls:
                    AppApply(load_stack(self.tmp_path)).delete(leftover)
                    orch_cls.return_value.render.assert_called_once()
        assert "no apps applied" in capsys.readouterr().out.lower()
        with pytest.raises(RuntimeError, match="not applied"):
            AppApply(load_stack(self.tmp_path)).delete("ghost")

    def test_apply_git_infers_source_and_deploys(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.git.side_effect = self.clone_side_effect(self._image_only_doc())
        orch = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch):
            with patch("raft.services.apply.load_stack", return_value=stack):
                name = self.applier(stack, shell).apply_git(
                    "git@github.com:org/img.git", deploy=True
                )
        assert name == "img"
        orch.ensure_app_deployed.assert_called_once_with(
            "img", ref_override="main", force_sync=False
        )

    def _image_only_doc(self) -> dict:
        return {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "img"},
            "spec": {
                "publicHost": "img.test",
                "image": "ghcr.io/org/img",
                "path": "apps/img",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }
