"""Apply / delete App manifests into the on-VPS registry (low-budget k8s)."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from raft.errors import OperatorError, app_not_applied, missing_manifest, raise_for_git_failure

from ...adapters.shell import Shell
from ...models.app_document import AppDocument
from ...models.manifest import CONTRACT_REL_PATH
from ...models.registry import AppRegistry
from ...models.stack import Stack, load_stack
from ...ui import say
from ..auth import GitAuthManager
from ..deploy.locking import app_and_stack_locks, app_deploy_lock
from .manifest_env import ManifestYamlLoader
from ..deploy.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


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
            raise missing_manifest(path)
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
        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
        try:
            tmp = self._checkout_git(tmp, repo, ref)
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
        with app_and_stack_locks(self.stack.root, name):
            if not AppRegistry(self.stack.root).delete(name):
                known = ", ".join(a.name for a in self.stack.apps) or "(none)"
                raise app_not_applied(name, known)
            say(f"deleted {name} from registry", style="ok")
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
        self._warn_missing_deps(app.name, app_spec.depends_on)
        with app_deploy_lock(self.stack.root, app.name):
            dest = AppRegistry(self.stack.root).write(data)
            self._announce_applied(app.name, dest, from_label)
            if deploy:
                self._deploy(app.name, ref_override=ref_override, force_sync=force_sync)
        return app.name

    def _parse_file_yaml(
        self, path: Path, env: Optional[Mapping[str, str]]
    ) -> dict[str, Any]:
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

    def _checkout_git(self, tmp: Path, repo: str, ref: str) -> Path:
        clone_urls = GitAuthManager(self.stack).clone_urls_for_repo(repo)
        last_exc: Optional[BaseException] = None
        for clone_url in clone_urls:
            shutil.rmtree(tmp, ignore_errors=True)
            tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
            try:
                tmp = self._clone_ref(tmp, clone_url, ref)
                if clone_url != repo:
                    logger.info("apply --git used auth Host alias URL %s", clone_url)
                return tmp
            except Exception as exc:
                last_exc = exc
                logger.debug("clone via %s failed: %s", clone_url, exc)
                continue
        assert last_exc is not None
        raise_for_git_failure(last_exc, repo, always=True)

    def _clone_ref(self, tmp: Path, clone_url: str, ref: str) -> Path:
        try:
            # capture=True: failed URL probes must not spam the terminal
            # (e.g. raw git@host before the Host-alias deploy key succeeds).
            self.sh.git(
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                ref,
                clone_url,
                str(tmp),
                capture=True,
            )
            return tmp
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            return self._clone_ref_full(clone_url, ref)

    def _clone_ref_full(self, clone_url: str, ref: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
        self.sh.git("clone", "--quiet", clone_url, str(tmp), capture=True)
        self.sh.git(
            "checkout",
            "-q",
            "-f",
            "--detach",
            ref,
            cwd=tmp,
            capture=True,
        )
        return tmp

    @staticmethod
    def _apply_ref_override(
        data: dict[str, Any], path: Path, ref_override: Optional[str]
    ) -> None:
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

    def _warn_missing_deps(self, name: str, depends_on: list[str]) -> None:
        known = {a.name for a in self.stack.apps}
        missing = [d for d in depends_on if d not in known and d != name]
        if not missing:
            return
        say(
            f"{name}: dependsOn not yet applied: {', '.join(missing)} "
            f"(ok if you apply them next)",
            style="warn",
        )

    def _announce_applied(
        self, name: str, dest: Path, from_label: Optional[str]
    ) -> None:
        rel = dest.relative_to(self.stack.root)
        if from_label:
            say(f"applied {name} from {from_label} → {rel}", style="ok")
        else:
            say(f"applied {name} → {rel}", style="ok")

    @staticmethod
    def _announce_delete_render(name: str, fresh: Stack) -> None:
        if fresh.apps:
            say(
                "re-rendered generated/; remove the Compose service if it is still running "
                f"(docker compose -f {fresh.root / 'compose.yaml'} rm -sf {name})",
                style="info",
            )
        else:
            say("re-rendered generated/ (no apps applied)", style="info")

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
