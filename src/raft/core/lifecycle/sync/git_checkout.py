"""Business git checkout workflow (clone / fetch / detach at ref)."""

import logging
import shutil
from pathlib import Path

from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App

from .git_gateway import GitGateway

logger = logging.getLogger(__name__)


class GitCheckoutService:
    """Bring a git-backed App tree to a resolved SHA under the data home."""

    def __init__(self, git: GitGateway) -> None:
        self._git = git

    def sync(
        self,
        app: App,
        dest: Path,
        clone_url: str,
        *,
        wanted: str,
        force: bool,
    ) -> str:
        logger.info("sync %s: git %s @ %s", app.name, clone_url, wanted)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_checkout(app, dest, clone_url)
        self._refuse_dirty(app, dest, force=force)
        self._fetch(app, dest, clone_url)
        sha = self._resolve_ref(app, dest, wanted)
        self._checkout_sha(app, dest, clone_url, sha)
        logger.info("sync %s: checked out %s", app.name, sha[:12])
        return sha

    def _ensure_checkout(self, app: App, dest: Path, clone_url: str) -> None:
        if not (dest / ".git").is_dir():
            self._clone_fresh(app, dest, clone_url)
            return
        try:
            self._git.set_remote_url(dest, clone_url)
        except Exception as exc:
            CheckedCommands.raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )

    def _clone_fresh(self, app: App, dest: Path, clone_url: str) -> None:
        self._prepare_clone_dest(app, dest)
        try:
            self._git.clone(clone_url, dest)
        except Exception as exc:
            CheckedCommands.raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )

    def _prepare_clone_dest(self, app: App, dest: Path) -> None:
        if not dest.exists() or not any(dest.iterdir()):
            return
        if self._is_contract_stub(dest):
            logger.info(
                "sync %s: replacing contract stub at %s with git clone",
                app.name,
                dest,
            )
            shutil.rmtree(dest)
            return
        raise OperatorError(
            f"{dest} exists but is not a git checkout.\n"
            f"Fix: move it aside, then: raft sync {app.name}"
        )

    @staticmethod
    def _is_contract_stub(dest: Path) -> bool:
        entries = [p.name for p in dest.iterdir()]
        return entries == [".raft"] or set(entries) <= {".raft"}

    def _refuse_dirty(self, app: App, dest: Path, *, force: bool) -> None:
        if force or not self._git.status_porcelain(dest):
            return
        raise OperatorError(
            f"{dest} has local changes.\n"
            f"Fix: commit/stash them, or: raft sync {app.name} --force"
        )

    def _fetch(self, app: App, dest: Path, clone_url: str) -> None:
        try:
            self._git.fetch(dest)
        except Exception as exc:
            CheckedCommands.raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )

    def _resolve_ref(self, app: App, dest: Path, wanted: str) -> str:
        checked = self._git.rev_parse(dest, wanted)
        if checked.returncode != 0:
            checked = self._git.rev_parse(dest, f"origin/{wanted}")
        if checked.returncode == 0:
            return checked.stdout.strip()
        raise OperatorError(
            f"cannot resolve ref {wanted!r} in {app.repo}.\n"
            f"Fix: raft sync {app.name} --ref <existing-branch-or-tag>"
        )

    def _checkout_sha(
        self, app: App, dest: Path, clone_url: str, sha: str
    ) -> None:
        try:
            self._git.checkout_detach(dest, sha)
        except Exception as exc:
            CheckedCommands.raise_for_git_failure(
                exc, app.repo or clone_url, app=app.name, always=True
            )
