"""Clone/update git-backed apps; pull images for docker sources; no-op for local."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from .auth import GitAuthManager
from ..models.inventory import App, Stack
from ..adapters.shell import Shell

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
                raise RuntimeError(f"local app path missing: {dest}")
            logger.info("sync %s: local (%s)", app.name, app.path)
            return

        if app.source == "docker":
            # Optional git checkout so the service repo can own .raft/app.yaml
            if app.repo:
                self._sync_git(app, dest, ref_override=ref_override, force=force)
            wanted = (ref_override or os.environ.get("VPS_SYNC_REF") or app.ref).strip()
            pull_ref = app.image_ref(wanted)
            pin = app.compose_pin_image
            logger.info("sync %s: docker pull %s", app.name, pull_ref)
            self.sh.docker("pull", pull_ref)
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
                # Allow a contract-only stub dir (local render) to be replaced by a real clone.
                entries = [p.name for p in dest.iterdir()]
                if entries == [".raft"] or set(entries) <= {".raft"}:
                    logger.info(
                        "sync %s: replacing contract stub at %s with git clone",
                        app.name,
                        dest,
                    )
                    shutil.rmtree(dest)
                else:
                    raise RuntimeError(
                        f"{dest} exists but is not a git checkout; "
                        "move it aside or set source=local"
                    )
            self.sh.git("clone", "--quiet", clone_url, str(dest))
        else:
            # Keep origin pointed at the auth-aware URL (deploy-key Host alias).
            self.sh.git("remote", "set-url", "origin", clone_url, cwd=dest)

        if not force and self._is_dirty(dest):
            raise RuntimeError(
                f"{dest} has local changes; commit/stash them or pass --force"
            )

        self.sh.git("fetch", "--prune", "--tags", "origin", cwd=dest)
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
            raise RuntimeError(f"cannot resolve ref {wanted!r} in {app.repo}")
        self.sh.git("checkout", "-f", "--detach", sha, cwd=dest)
        if app.source != "docker":
            state = self.stack.ref_state_file(app)
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(f"{sha}\n# requested: {wanted}\n", encoding="utf-8")
        logger.info("sync %s: checked out %s", app.name, sha[:12])

    def _is_dirty(self, repo: Path) -> bool:
        result = self.sh.git("status", "--porcelain", cwd=repo, capture=True)
        return bool(result.stdout.strip())
