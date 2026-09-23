"""Apply / delete App manifests into the on-VPS registry."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.auth import GitAuthManager
from raft.services.manifest_env import ApplyEnvSources
from raft.services.render import StackRenderer

from ..base import RaftTestCase, write_applied_app
from .base import ServicesTestCase
from .fixtures import (
    CI_TO_CONTAINER_APPLY_ENV,
    CI_TO_CONTAINER_ENV_MANIFEST,
    CI_TO_CONTAINER_FLAG_OVERRIDES,
    MISSING_VAR_FILE_MANIFEST,
    PLACEHOLDER_FILE_MANIFEST,
    clone_writes_missing_var_manifest,
    clone_writes_placeholder_manifest,
)
def _apply(stack, shell):
    applier = AppApply(stack)
    applier.sh = shell
    return applier


def _manifest(
    name: str = "web",
    *,
    source: str = "local",
    public_host: str = "web.test",
    **spec_extra,
) -> dict:
    spec = {
        "publicHost": public_host,
        "source": source,
        "path": f"apps/{name}",
        "ref": "main",
        "www": True,
        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
        "build": {"context": "."},
        **spec_extra,
    }
    return {
        "apiVersion": "raft/v1",
        "kind": "App",
        "metadata": {"name": name},
        "spec": spec,
    }


class TestAppApply(RaftTestCase):
    def test_apply_file_no_deploy(self, capsys) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
        stack = load_stack(self.tmp_path)
        name = AppApply(stack).apply_file(path, deploy=False)
        assert name == "web"
        assert (self.tmp_path / "state" / "apps" / "web.yaml").is_file()
        assert "applied web" in capsys.readouterr().out

    def test_apply_file_rejects_non_mapping(self) -> None:
        path = self.tmp_path / "bad.yaml"
        path.write_text("- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)

    def test_apply_file_missing_and_bad_yaml(self) -> None:
        missing = self.tmp_path / "nope.yaml"
        with pytest.raises(RuntimeError, match="cannot read App manifest"):
            AppApply(load_stack(self.tmp_path)).apply_file(missing, deploy=False)
        path = self.tmp_path / "bad.yaml"
        path.write_text("{{{{", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid App manifest YAML"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)

    def test_apply_file_ref_override_and_bad_spec(self) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(
            yaml.safe_dump(_manifest()),
            encoding="utf-8",
        )
        AppApply(load_stack(self.tmp_path)).apply_file(path, ref_override="v2", deploy=False)
        data = yaml.safe_load(
            (self.tmp_path / "state" / "apps" / "web.yaml").read_text(encoding="utf-8")
        )
        assert data["spec"]["ref"] == "v2"

        path.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: x\nspec: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="spec must be an object"):
            AppApply(load_stack(self.tmp_path)).apply_file(path, ref_override="x", deploy=False)

    def test_apply_file_deploys_running_and_new(self) -> None:
        path = self.tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
        stack = load_stack(self.tmp_path)
        applier = AppApply(stack)

        orch = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch):
            with patch("raft.services.apply.load_stack", return_value=stack):
                applier.apply_file(path, deploy=True)
        orch.ensure_app_deployed.assert_called_once_with(
            "web", ref_override=None, force_sync=False
        )

        orch2 = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch2):
            with patch("raft.services.apply.load_stack", return_value=stack):
                applier.apply_file(path, deploy=True, force_sync=True)
        orch2.ensure_app_deployed.assert_called_once_with(
            "web", ref_override=None, force_sync=True
        )

    def test_apply_git_shallow_and_fallback(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()

        def clone_then_checkout(*args, **kwargs):
            cwd = kwargs.get("cwd")
            dest = Path(args[-1]) if cwd is None else Path(cwd)
            if "clone" in args:
                target = Path(args[-1])
                (target / ".raft").mkdir(parents=True, exist_ok=True)
                (target / ".raft" / "app.yaml").write_text(
                    yaml.safe_dump(
                        _manifest(
                            "hub",
                            source="docker",
                            public_host="hub.test",
                            image="ghcr.io/org/hub",
                        )
                    ),
                    encoding="utf-8",
                )
                data = yaml.safe_load((target / ".raft" / "app.yaml").read_text(encoding="utf-8"))
                data["spec"].pop("build", None)
                (target / ".raft" / "app.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

        shell.git.side_effect = clone_then_checkout
        name = _apply(stack, shell).apply_git(
            "git@github.com:org/hub.git", ref="main", deploy=False
        )
        assert name == "hub"
        assert shell.git.call_count >= 1

        calls = {"n": 0}

        def fail_shallow_then_ok(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("shallow failed")
            target = Path(args[-1]) if "clone" in args else Path(kwargs["cwd"])
            if "clone" in args:
                target.mkdir(parents=True, exist_ok=True)
                (target / ".raft").mkdir(parents=True, exist_ok=True)
                doc = _manifest("gitapp", source="git", repo="git@github.com:org/x.git")
                doc["spec"].pop("image", None)
                (target / ".raft" / "app.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")

        shell2 = MagicMock()
        shell2.git.side_effect = fail_shallow_then_ok
        name2 = _apply(stack, shell2).apply_git(
            "git@github.com:org/x.git", ref="dev", deploy=False
        )
        assert name2 == "gitapp"

    def test_apply_git_missing_manifest_and_bad_docs(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()

        def empty_clone(*args, **kwargs):
            Path(args[-1]).mkdir(parents=True, exist_ok=True)

        shell.git.side_effect = empty_clone
        with pytest.raises(RuntimeError, match="app.yaml"):
            _apply(stack, shell).apply_git("git@x/y.git", deploy=False)

        def list_doc(*args, **kwargs):
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            (target / ".raft" / "app.yaml").write_text("- x\n", encoding="utf-8")

        shell.git.side_effect = list_doc
        with pytest.raises(RuntimeError, match="mapping"):
            _apply(stack, shell).apply_git("git@x/y.git", deploy=False)

        def bad_spec(*args, **kwargs):
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            (target / ".raft" / "app.yaml").write_text(
                "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: z\nspec: []\n",
                encoding="utf-8",
            )

        shell.git.side_effect = bad_spec
        with pytest.raises(ValueError, match="spec must be an object"):
            _apply(stack, shell).apply_git("git@x/y.git", deploy=False)

    def test_apply_git_auth_failure_hints_setup(self) -> None:
        import subprocess

        stack = load_stack(self.tmp_path)
        shell = MagicMock()

        def denied(*args, **kwargs):
            raise subprocess.CalledProcessError(
                128,
                args,
                stderr="git@github.com: Permission denied (publickey).\n",
            )

        shell.git.side_effect = denied
        with pytest.raises(RuntimeError, match="auth setup .* --repo"):
            _apply(stack, shell).apply_git(
                "git@github.com:Playloft-Studio/playloftstudio.com.git",
                deploy=False,
            )

    def test_apply_git_non_auth_clone_error_reraises(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.git.side_effect = RuntimeError("network unreachable")
        with pytest.raises(RuntimeError, match="cannot reach git host"):
            _apply(stack, shell).apply_git("git@github.com:org/x.git", deploy=False)

    def test_apply_git_bad_manifest_yaml(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()

        def clone(*args, **kwargs):
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            (target / ".raft" / "app.yaml").write_text("{{{{", encoding="utf-8")
            return MagicMock(returncode=0)

        shell.git.side_effect = clone
        with pytest.raises(RuntimeError, match="invalid App manifest YAML"):
            _apply(stack, shell).apply_git("git@github.com:org/x.git", deploy=False)

    def test_apply_git_retries_host_alias(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        auth_dir = self.tmp_path / "ssh-apply"
        mgr = GitAuthManager(stack)
        mgr.sh = shell
        mgr.ssh_dir = auth_dir
        mgr.keys_dir = auth_dir / "raft"
        mgr.config_path = auth_dir / "config"
        ServicesTestCase.write_keypair(mgr, "playloftstudio")

        calls: list[str] = []

        def clone_alias(*args, **kwargs):
            if "clone" not in args:
                return MagicMock(returncode=0)
            url = args[-2]
            calls.append(url)
            if "raft-playloftstudio" not in url:
                raise RuntimeError("Permission denied (publickey)")
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            (target / ".raft" / "app.yaml").write_text(
                yaml.safe_dump(
                    _manifest(
                        "playloftstudio",
                        source="git",
                        repo="git@github.com:Playloft-Studio/playloftstudio.com.git",
                        public_host="playloftstudio.com",
                    )
                ),
                encoding="utf-8",
            )

        shell.git.side_effect = clone_alias
        with patch("raft.services.apply.GitAuthManager", return_value=mgr):
            name = _apply(stack, shell).apply_git(
                "git@github.com:Playloft-Studio/playloftstudio.com.git",
                deploy=False,
            )
        assert name == "playloftstudio"
        assert any("raft-playloftstudio" in u for u in calls)

    def test_delete_re_renders(self, capsys) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test")
        write_applied_app(self.tmp_path, "other", public_host="other.test")
        stack = load_stack(self.tmp_path)
        with patch("raft.services.apply.Orchestrator") as orch_cls:
            AppApply(stack).delete("web")
            orch_cls.assert_called_once()
            orch_cls.return_value.render.assert_called_once()
        assert not (self.tmp_path / "state" / "apps" / "web.yaml").is_file()
        assert "deleted web" in capsys.readouterr().out

        with patch("raft.services.apply.Orchestrator") as orch_cls:
            AppApply(load_stack(self.tmp_path)).delete("other")
            orch_cls.return_value.render.assert_called_once()
        assert "no apps applied" in capsys.readouterr().out.lower() or True

        with pytest.raises(RuntimeError, match="not applied"):
            AppApply(load_stack(self.tmp_path)).delete("ghost")

    def test_apply_git_infers_source_and_deploys(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()

        def clone_image_app(*args, **kwargs):
            target = Path(args[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / ".raft").mkdir(parents=True, exist_ok=True)
            (target / ".raft" / "app.yaml").write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "raft/v1",
                        "kind": "App",
                        "metadata": {"name": "img"},
                        "spec": {
                            "publicHost": "img.test",
                            "image": "ghcr.io/org/img",
                            "path": "apps/img",
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": 80,
                                    "expose": "http",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

        shell.git.side_effect = clone_image_app
        orch = MagicMock()
        with patch("raft.services.apply.Orchestrator", return_value=orch):
            with patch("raft.services.apply.load_stack", return_value=stack):
                name = _apply(stack, shell).apply_git(
                    "git@github.com:org/img.git", deploy=True
                )
        assert name == "img"
        orch.ensure_app_deployed.assert_called_once_with(
            "img", ref_override="main", force_sync=False
        )

    def test_apply_file_expands_env_into_registry_before_parse(self) -> None:
        """Expand happens before YAML parse; registry stores concrete values.

        Caller merges process → --env-file → --env once, then passes ``env=``.
        """
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(PLACEHOLDER_FILE_MANIFEST, encoding="utf-8")
        env_file = self.tmp_path / "apply.env"
        env_file.write_text("RAFT_APP_NAME=from-file\n", encoding="utf-8")
        apply_env = ApplyEnvSources(
            environ={"RAFT_APP_NAME": "from-process"},
            env_file=env_file,
            overrides=["RAFT_APP_NAME=expanded-web"],
        ).build()

        applied_name = AppApply(load_stack(self.tmp_path)).apply_file(
            manifest,
            deploy=False,
            env=apply_env,
        )

        registry_path = self.tmp_path / "state" / "apps" / f"{applied_name}.yaml"
        registry_text = registry_path.read_text(encoding="utf-8")
        registry = yaml.safe_load(registry_text)

        assert applied_name == "expanded-web"
        assert registry["metadata"]["name"] == "expanded-web"
        assert registry["spec"]["publicHost"] == "web.test"  # :-default
        assert registry["spec"]["path"] == "apps/expanded-web"
        assert "${" not in registry_text

    def test_apply_file_missing_var_fails(self) -> None:
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(MISSING_VAR_FILE_MANIFEST, encoding="utf-8")

        with pytest.raises(RuntimeError, match="undefined variable MISSING") as caught:
            AppApply(load_stack(self.tmp_path)).apply_file(
                manifest, deploy=False, env={}
            )

        error = str(caught.value)
        assert "MISSING" in error

    def test_apply_expands_ci_env_into_container_spec_then_compose(self) -> None:
        """Finalized apply ``env`` fills ``spec.env`` templates; render → Compose.

        Bridge (required in app.yaml):
          container key (Docker) ← ``${CI_TEMPLATE}`` (apply-time name)

        Merge (process → flags) happens before ``apply_file``; apply only expands.
        ``LOG_LEVEL`` uses ``${CI_LOG_LEVEL:-info}`` (default when CI omits it).
        """
        manifest = self.tmp_path / "manifest.yaml"
        manifest.write_text(CI_TO_CONTAINER_ENV_MANIFEST, encoding="utf-8")
        apply_env = ApplyEnvSources(
            environ=CI_TO_CONTAINER_APPLY_ENV,
            overrides=CI_TO_CONTAINER_FLAG_OVERRIDES,
        ).build()

        applied_name = AppApply(load_stack(self.tmp_path)).apply_file(
            manifest,
            deploy=False,
            env=apply_env,
        )

        registry = yaml.safe_load(
            (self.tmp_path / "state" / "apps" / f"{applied_name}.yaml").read_text(
                encoding="utf-8"
            )
        )
        container_env = registry["spec"]["env"]

        assert applied_name == "api-dev"
        assert registry["spec"]["envFile"] == "/home/raft/.raft/api-dev.env"
        assert container_env["DATABASE_URL"] == "postgres://from-ci-flag"
        assert container_env["LOG_LEVEL"] == "info"
        assert "${" not in yaml.safe_dump(registry)

        StackRenderer(load_stack(self.tmp_path)).render()
        compose = (
            self.tmp_path / "generated" / "compose.apps.yaml"
        ).read_text(encoding="utf-8")

        assert "environment:" in compose
        assert 'DATABASE_URL: "postgres://from-ci-flag"' in compose
        assert "LOG_LEVEL: info" in compose
        assert "env_file:" in compose
        assert "/home/raft/.raft/api-dev.env" in compose

    def test_apply_git_expands_env_into_registry(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.git.side_effect = clone_writes_placeholder_manifest

        applied_name = _apply(stack, shell).apply_git(
            "git@github.com:org/x.git",
            deploy=False,
            env={"APP_NAME": "from-git"},
        )

        registry_path = self.tmp_path / "state" / "apps" / f"{applied_name}.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))

        assert applied_name == "from-git"
        assert registry["metadata"]["name"] == "from-git"
        assert registry["spec"]["path"] == "apps/from-git"

    def test_apply_git_missing_var_fails(self) -> None:
        stack = load_stack(self.tmp_path)
        shell = MagicMock()
        shell.git.side_effect = clone_writes_missing_var_manifest

        with pytest.raises(RuntimeError, match="undefined variable MISSING") as caught:
            _apply(stack, shell).apply_git(
                "git@github.com:org/x.git",
                deploy=False,
                env={},
            )

        error = str(caught.value)
        assert "MISSING" in error
