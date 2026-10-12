"""Clone a git ref into a temp tree for ``raft apply --git``."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from raft.core.platform.adapters.shell import Shell
from raft.core.platform.auth import GitAuthManager
from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.models.stack import Stack

logger = logging.getLogger(__name__)


class GitManifestCheckout:
    """Clone ``repo@ref`` via auth Host aliases, shallow then full fallback."""

    def __init__(self, stack: Stack, sh: Shell) -> None:
        self.stack = stack
        self.sh = sh

    def checkout(self, repo: str, ref: str) -> Path:
        """Return a temp checkout path; caller must ``rmtree`` when done."""
        tmp = Path(tempfile.mkdtemp(prefix="raft-apply-"))
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
        CheckedCommands.raise_for_git_failure(last_exc, repo, always=True)

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
