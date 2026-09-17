"""Clone/update git-backed apps; pull images for docker sources; no-op for local."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from ..adapters.shell import Shell
from ..models.app import App
from ..models.stack import Stack
from raft.errors import OperatorError, raise_for_docker_pull_failure, raise_for_git_failure

from .auth import GitAuthManager

logger = logging.getLogger(__name__)


class SourceSync:
    def __init__(
        self,
        stack: Stack,
        shell: Shell,
        *,
        auth: Optional[GitAuthManager] = None,
    ) -> None:
        self.stack = stack
        self.sh = shell
        self.auth = auth or GitAuthManager(stack, shell)

    def sync(
        self,
        apps: Optional[list[App]] = None,
        *,
        ref_override: Optional[str] = None,
        force: bool = False,
    ) -> None:
        targets = apps if apps is not None else list(self.stack.apps)
        for app in targets:
            self._sync_one(app, ref_override=ref_override, force=force)

    def _sync_one(
        self,
        app: App,
        *,
        ref_override: Optional[str],
        force: bool,
    ) -> None:
        dest = app.abs_path(self.stack.root)
        if app.source == "local":
            if not dest.is_dir():
                raise OperatorError(
                    f"local app path missing: {dest}\n"
                    f"Fix: create/copy the tree under {app.path}, or change "
                    f"spec.source / re-apply the App"
                )
            logger.info("sync %s: local (%s)", app.name, app.path)
            return

        if app.source == "docker":
            if app.repo:
                self._sync_git(app, dest, ref_override=ref_override, force=force)
            wanted = (ref_override or os.environ.get("VPS_SYNC_REF") or app.ref).strip()
            pull_ref = app.image_ref(wanted)
            pin = app.compose_pin_image
            logger.info("sync %s: docker pull %s", app.name, pull_ref)
            self._docker_pull(pull_ref, app=app.name, repo=app.repo)
            if pull_ref != pin:
                logger.info("sync %s: tag %s -> %s (compose pin)", app.name, pull_ref, pin)
                self.sh.docker("tag", pull_ref, pin)
            digest = self.sh.docker(
                "image",
                "inspect",
                "-f",
                "{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}",
                pin,
                capture=True,
            ).stdout.strip()
            state = self.stack.ref_state_file(app)
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(
                f"{digest}\n# pulled: {pull_ref}\n# pin: {pin}\n# requested: {wanted}\n",
                encoding="utf-8",
            )
            logger.info("sync %s: ready at %s", app.name, digest[:64])
            return

        assert app.repo
        self._sync_git(app, dest, ref_override=ref_override, force=force)

    def _docker_pull(
        self,
        image: str,
        *,
        app: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        result = self.sh.docker("pull", image, capture=True, check=False)
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout or "").strip()
        raise_for_docker_pull_failure(
            image, detail=detail, app=app, repo=repo
        )

    def _sync_git(
        self,
        app: App,
        dest: Path,
        *,
        ref_override: Optional[str],
        force: bool,
    ) -> None:
        assert app.repo
        clone_url = self.auth.effective_clone_url(app)
        wanted = (ref_override or os.environ.get("VPS_SYNC_REF") or app.ref).strip()
        logger.info("sync %s: git %s @ %s", app.name, clone_url, wanted)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not (dest / ".git").is_dir():
            if dest.exists() and any(dest.iterdir()):
                entries = [p.name for p in dest.iterdir()]
                if entries == [".raft"] or set(entries) <= {".raft"}:
                    logger.info(
                        "sync %s: replacing contract stub at %s with git clone",
                        app.name,
                        dest,
                    )
                    shutil.rmtree(dest)
                else:
                    raise OperatorError(
                        f"{dest} exists but is not a git checkout.\n"
                        f"Fix: move it aside, then: raft sync {app.name}"
                    )
            try:
                self.sh.git("clone", "--quiet", clone_url, str(dest), capture=True)
            except Exception as exc:
                raise_for_git_failure(
                    exc, app.repo or clone_url, app=app.name, always=True
                )
        else:
            try:
                self.sh.git(
                    "remote", "set-url", "origin", clone_url, cwd=dest, capture=True
                )
            except Exception as exc:
                raise_for_git_failure(
                    exc, app.repo or clone_url, app=app.name, always=True
                )

        if not force and self._is_dirty(dest):
            raise OperatorError(
                f"{dest} has local changes.\n"
                f"Fix: commit/stash them, or: raft sync {app.name} --force"
            )

        try:
            self.sh.git(
                "fetch", "--prune", "--tags", "origin", cwd=dest, capture=True
            )
        except Exception as exc:
            raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )

        checked = self.sh.git(
            "rev-parse",
            "--verify",
            wanted,
            cwd=dest,
            check=False,
            capture=True,
        )
        if checked.returncode != 0:
            checked = self.sh.git(
                "rev-parse",
                "--verify",
                f"origin/{wanted}",
                cwd=dest,
                check=False,
                capture=True,
            )
        if checked.returncode == 0:
            sha = checked.stdout.strip()
        else:
            raise OperatorError(
                f"cannot resolve ref {wanted!r} in {app.repo}.\n"
                f"Fix: raft sync {app.name} --ref <existing-branch-or-tag>"
            )
        try:
            self.sh.git("checkout", "-q", "-f", "--detach", sha, cwd=dest, capture=True)
        except Exception as exc:
            raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )
        if app.source != "docker":
            state = self.stack.ref_state_file(app)
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(f"{sha}\n# requested: {wanted}\n", encoding="utf-8")
        logger.info("sync %s: checked out %s", app.name, sha[:12])

    def _is_dirty(self, repo: Path) -> bool:
        result = self.sh.git("status", "--porcelain", cwd=repo, capture=True)
        return bool(result.stdout.strip())
