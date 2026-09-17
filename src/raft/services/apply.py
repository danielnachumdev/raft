"""Apply / delete App manifests into the on-VPS registry (low-budget k8s)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from raft.errors import OperatorError, app_not_applied, missing_manifest, raise_for_git_failure

from ..adapters.shell import Shell
from ..models.manifest import (
    CONTRACT_REL_PATH,
    contract_path,
    delete_registry_app,
    parse_app_document,
    write_registry_app,
)
from ..models.stack import Stack, load_stack
from ..ui import say
from .auth import GitAuthManager
from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class AppApply:
    def __init__(self, stack: Stack, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)

    def apply_file(
        self,
        path: Path,
        *,
        ref_override: Optional[str] = None,
        deploy: bool = True,
        force_sync: bool = False,
    ) -> str:
        if not path.is_file():
            raise missing_manifest(path)
        try:
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid App manifest YAML at {path}: {exc}\n"
                f"Fix: repair the YAML (apiVersion/kind/metadata/spec) — "
                f"see examples/*/ .raft/app.yaml"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: document must be a mapping")
        if ref_override:
            spec = data.setdefault("spec", {})
            if not isinstance(spec, dict):
                raise ValueError(f"{path}: spec must be an object")
            spec["ref"] = ref_override
        app, _ = parse_app_document(data, path=path)
        dest = write_registry_app(self.stack.root, data)
        say(f"applied {app.name} → {dest.relative_to(self.stack.root)}", style="ok")
        if deploy:
            self._deploy(app.name, ref_override=ref_override, force_sync=force_sync)
        return app.name

    def apply_git(
        self,
        repo: str,
        *,
        ref: str = "main",
        deploy: bool = True,
        force_sync: bool = False,
    ) -> str:
        auth = GitAuthManager(self.stack, self.sh)
        clone_urls = auth.clone_urls_for_repo(repo)
        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
        last_exc: Optional[BaseException] = None
        try:
            cloned = False
            for clone_url in clone_urls:
                shutil.rmtree(tmp, ignore_errors=True)
                tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
                try:
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
                    except Exception:
                        shutil.rmtree(tmp, ignore_errors=True)
                        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
                        self.sh.git(
                            "clone", "--quiet", clone_url, str(tmp), capture=True
                        )
                        self.sh.git(
                            "checkout",
                            "-q",
                            "-f",
                            "--detach",
                            ref,
                            cwd=tmp,
                            capture=True,
                        )
                    cloned = True
                    if clone_url != repo:
                        logger.info("apply --git used auth Host alias URL %s", clone_url)
                    break
                except Exception as exc:
                    last_exc = exc
                    logger.debug("clone via %s failed: %s", clone_url, exc)
                    continue

            if not cloned:
                assert last_exc is not None
                raise_for_git_failure(last_exc, repo, always=True)

            manifest = contract_path(tmp)
            if not manifest.is_file():
                raise OperatorError(
                    f"no {CONTRACT_REL_PATH.as_posix()} in {repo}@{ref}\n"
                    f"Fix: add that file on the ref, or: raft apply --git {repo} --ref <other>"
                )
            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
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
            spec = data.setdefault("spec", {})
            if not isinstance(spec, dict):
                raise ValueError("spec must be an object")
            spec.setdefault("repo", repo)
            spec["ref"] = ref
            if not spec.get("source"):
                spec["source"] = "docker" if spec.get("image") else "git"
            app, _ = parse_app_document(data, path=manifest)
            dest = write_registry_app(self.stack.root, data)
            say(
                f"applied {app.name} from {repo}@{ref} → "
                f"{dest.relative_to(self.stack.root)}",
                style="ok",
            )
            if deploy:
                self._deploy(app.name, ref_override=ref, force_sync=force_sync)
            return app.name
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def delete(self, name: str) -> None:
        if not delete_registry_app(self.stack.root, name):
            known = ", ".join(a.name for a in self.stack.apps) or "(none)"
            raise app_not_applied(name, known)
        say(f"deleted {name} from registry", style="ok")
        fresh = load_stack(self.stack.root)
        Orchestrator(fresh).render()
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
        orch = Orchestrator(load_stack(self.stack.root))
        orch.ensure_app_deployed(name, ref_override=ref_override, force_sync=force_sync)
