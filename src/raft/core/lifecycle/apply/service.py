"""Apply / delete App manifests into the on-VPS registry (low-budget k8s)."""

import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from raft.core.platform.adapters.shell import Shell
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.platform.locking import AppAndStackLocks, AppDeployLock
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.depends_cycle import DependsOnCycleGuard
from raft.core.core.models.manifest import CONTRACT_REL_PATH
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.stack import Stack, load_stack
from raft.core.platform.secrets import AppSecretsLayout
from raft.core.core.ui import OperatorSay
from .git_checkout import GitManifestCheckout
from .preprocess.yaml_loader import ManifestYamlLoader


class AppApply:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)

    def apply_file(
        self,
        path: Path,
        *,
        ref_override: Optional[str] = None,
        deploy: bool = True,
        force_sync: bool = False,
        env: Optional[Mapping[str, str]] = None,
    ) -> str:
        if not path.is_file():
            raise DomainErrors.missing_manifest(path)
        data = self._parse_file_yaml(path, env)
        self._apply_ref_override(data, path, ref_override)
        return self._register_manifest(
            data,
            path=path,
            deploy=deploy,
            force_sync=force_sync,
            ref_override=ref_override,
        )

    def apply_git(
        self,
        repo: str,
        *,
        ref: str = "main",
        deploy: bool = True,
        force_sync: bool = False,
        env: Optional[Mapping[str, str]] = None,
    ) -> str:
        tmp = GitManifestCheckout(self.stack, self.sh).checkout(repo, ref)
        try:
            data, manifest = self._parse_git_yaml(tmp, repo, ref, env)
            self._stamp_git_spec(data, repo, ref)
            return self._register_manifest(
                data,
                path=manifest,
                deploy=deploy,
                force_sync=force_sync,
                ref_override=ref,
                from_label=f"{repo}@{ref}",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def delete(self, name: str) -> None:
        with AppAndStackLocks(self.stack.root, name):
            if not AppRegistry(self.stack.root).delete(name):
                known = ", ".join(a.name for a in self.stack.apps) or "(none)"
                raise DomainErrors.app_not_applied(name, known)
            OperatorSay.say(f"deleted {name} from registry", style="ok")
            fresh = load_stack(self.stack.root)
            Orchestrator(fresh).render()
            self._announce_delete_render(name, fresh)

    def _register_manifest(
        self,
        data: dict[str, Any],
        *,
        path: Path,
        deploy: bool,
        force_sync: bool,
        ref_override: Optional[str],
        from_label: Optional[str] = None,
    ) -> str:
        app, app_spec = AppDocument.parse(data, path=path)
        self._warn_missing_deps(app.name, app_spec.depend_names())
        DependsOnCycleGuard(self.stack.root).reject(app.name, app_spec.depends_on)
        with AppDeployLock(self.stack.root, app.name):
            dest = AppRegistry(self.stack.root).write(data)
            AppSecretsLayout(self.stack.root).ensure_app_dir(app.name)
            self._announce_applied(app.name, dest, from_label)
            if deploy:
                self._deploy(app.name, ref_override=ref_override, force_sync=force_sync)
        return app.name

    def _parse_file_yaml(self, path: Path, env: Optional[Mapping[str, str]]) -> dict[str, Any]:
        try:
            data = ManifestYamlLoader(env=self._expansion_env(env)).load(
                path.read_text(encoding="utf-8"),
                path=path,
            )
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid App manifest YAML at {path}: {exc}\n"
                f"Fix: repair the YAML (apiVersion/kind/metadata/spec) — "
                f"see examples/*/ .raft/app.yaml"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: document must be a mapping")
        return data

    def _parse_git_yaml(
        self,
        tmp: Path,
        repo: str,
        ref: str,
        env: Optional[Mapping[str, str]],
    ) -> tuple[dict[str, Any], Path]:
        manifest = self._require_git_manifest(tmp, repo, ref)
        try:
            data = ManifestYamlLoader(env=self._expansion_env(env)).load(
                manifest.read_text(encoding="utf-8"),
                path=f"{repo}@{ref}:{CONTRACT_REL_PATH.as_posix()}",
            )
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid App manifest YAML in {repo}@{ref}: {exc}\n"
                f"Fix: repair .raft/app.yaml in the repo"
            ) from exc
        if not isinstance(data, dict):
            raise OperatorError(
                f"app manifest must be a mapping in {repo}@{ref}\n"
                f"Fix: repair .raft/app.yaml in the repo"
            )
        return data, manifest

    @staticmethod
    def _require_git_manifest(tmp: Path, repo: str, ref: str) -> Path:
        manifest = AppDocument.contract_path(tmp)
        if manifest.is_file():
            return manifest
        raise OperatorError(
            f"no {CONTRACT_REL_PATH.as_posix()} in {repo}@{ref}\n"
            f"Fix: add that file on the ref, or: raft apply --git {repo} --ref <other>"
        )

    @staticmethod
    def _apply_ref_override(data: dict[str, Any], path: Path, ref_override: Optional[str]) -> None:
        if not ref_override:
            return
        spec = data.setdefault("spec", {})
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: spec must be an object")
        spec["ref"] = ref_override

    @staticmethod
    def _stamp_git_spec(data: dict[str, Any], repo: str, ref: str) -> None:
        spec = data.setdefault("spec", {})
        if not isinstance(spec, dict):
            raise ValueError("spec must be an object")
        spec.setdefault("repo", repo)
        spec["ref"] = ref
        if not spec.get("source"):
            spec["source"] = "docker" if spec.get("image") else "git"

    def _warn_missing_deps(self, name: str, depends_on: tuple[str, ...]) -> None:
        known = {a.name for a in self.stack.apps}
        missing = [d for d in depends_on if d not in known and d != name]
        if not missing:
            return
        OperatorSay.say(
            f"{name}: dependsOn not yet applied: {', '.join(missing)} "
            f"(ok if you apply them next)",
            style="warn",
        )

    def _announce_applied(self, name: str, dest: Path, from_label: Optional[str]) -> None:
        rel = dest.relative_to(self.stack.root)
        if from_label:
            OperatorSay.say(f"applied {name} from {from_label} → {rel}", style="ok")
        else:
            OperatorSay.say(f"applied {name} → {rel}", style="ok")

    @staticmethod
    def _announce_delete_render(name: str, fresh: Stack) -> None:
        if fresh.apps:
            OperatorSay.say(
                "re-rendered generated/; remove the Compose service if it is still running "
                f"(docker compose -f {fresh.root / 'compose.yaml'} rm -sf {name})",
                style="info",
            )
        else:
            OperatorSay.say("re-rendered generated/ (no apps applied)", style="info")

    def _deploy(
        self,
        name: str,
        *,
        ref_override: Optional[str],
        force_sync: bool,
    ) -> None:
        # App lock already held by apply; ensure_app_deployed re-enters it.
        orch = Orchestrator(load_stack(self.stack.root))
        orch.ensure_app_deployed(name, ref_override=ref_override, force_sync=force_sync)

    @staticmethod
    def _expansion_env(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
        """Use the caller's finalized map, or process env when omitted."""
        return os.environ if env is None else env
