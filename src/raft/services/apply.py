"""Apply / delete App manifests into the on-VPS registry (low-budget k8s)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yaml

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


def _looks_like_git_auth_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    if isinstance(exc, subprocess.CalledProcessError):
        text = f"{text} {(exc.stderr or '')} {(exc.output or '')}".lower()
    needles = (
        "permission denied (publickey)",
        "could not read from remote repository",
        "host key verification failed",
        "authentication failed",
        "publickey",
    )
    return any(n in text for n in needles)


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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
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
                if _looks_like_git_auth_failure(last_exc):
                    raise RuntimeError(
                        f"git clone failed (SSH auth) for {repo!r}. "
                        f"Set up a read-only deploy key first, then retry:\n"
                        f"  raft auth setup <app-name> --repo {repo}\n"
                        f"  # paste the pubkey as a Deploy key on the repo\n"
                        f"  raft auth test <app-name> --repo {repo}\n"
                        f"  raft apply --git {repo} --ref {ref}"
                    ) from last_exc
                raise last_exc

            manifest = contract_path(tmp)
            if not manifest.is_file():
                raise FileNotFoundError(f"no {CONTRACT_REL_PATH.as_posix()} in {repo}@{ref}")
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("app manifest must be a mapping")
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
            raise KeyError(f"app {name!r} is not applied")
        say(f"deleted {name} from registry", style="ok")
        fresh = load_stack(self.stack.root)
        Orchestrator(fresh).render()
        if fresh.apps:
            say(
                "re-rendered generated/; remove the Compose service if it is still running",
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
