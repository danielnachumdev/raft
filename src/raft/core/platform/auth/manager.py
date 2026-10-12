"""Per-service read-only SSH deploy keys for private git sources."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from raft.core.platform.adapters.host import HostGateway
from raft.core.platform.adapters.shell import Shell
from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from .clone_urls import CloneUrlMapper
from .instructions import DeployKeyInstructions
from .keys import SshDeployKeys
from .repo import RepoUrlResolver
from .url import SshGitUrl
from .urls import SshGitUrls

logger = logging.getLogger(__name__)


class GitAuthManager:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.keys = SshDeployKeys(Shell(stack.root))
        self.urls = SshGitUrls()
        self._repos = RepoUrlResolver(stack)
        self._clones = CloneUrlMapper(self.urls, self.keys)
        self._instructions = DeployKeyInstructions()

    @property
    def sh(self) -> Shell:
        return self.keys.sh

    @sh.setter
    def sh(self, value: Shell) -> None:
        self.keys.sh = value

    @property
    def ssh_dir(self) -> Path:
        return self.keys.ssh_dir

    @ssh_dir.setter
    def ssh_dir(self, value: Path) -> None:
        self.keys.ssh_dir = value

    @property
    def keys_dir(self) -> Path:
        return self.keys.keys_dir

    @keys_dir.setter
    def keys_dir(self, value: Path) -> None:
        self.keys.keys_dir = value

    @property
    def config_path(self) -> Path:
        return self.keys.config_path

    @config_path.setter
    def config_path(self, value: Path) -> None:
        self.keys.config_path = value

    def key_path(self, service: str) -> Path:
        return self.keys.key_path(service)

    def pub_path(self, service: str) -> Path:
        return self.keys.pub_path(service)

    def is_configured(self, service: str) -> bool:
        return self.keys.is_configured(service)

    def effective_clone_url(self, app: App) -> str:
        return self._clones.effective(app)

    def resolve_repo_url(self, service: str, repo: Optional[str] = None) -> str:
        return self._repos.resolve(service, repo)

    def setup(
        self,
        service: str,
        *,
        force: bool = False,
        repo: Optional[str] = None,
    ) -> None:
        repo_url = self.resolve_repo_url(service, repo)
        parsed = self.urls.parse(repo_url)
        base_host = self.urls.real_git_host(service, parsed.host)
        alias = self.urls.host_alias(service, base_host)
        self.keys.ensure_layout()
        self._prepare_key(service, force=force)
        self.keys.upsert_ssh_config(service, alias=alias, hostname=base_host)
        logger.info("auth %s: SSH Host %s → %s", service, alias, base_host)
        self._announce_key(service, base_host, parsed)
        logger.info("auth %s: clone URL will be %s", service, parsed.with_host_alias(alias))
        applied = any(a.name == service for a in self.stack.apps)
        self._instructions.say_next_steps(service, repo_url, applied=applied)

    def _prepare_key(self, service: str, *, force: bool) -> None:
        existed = self.is_configured(service)
        if existed and not force:
            logger.info("auth %s: key already exists (%s)", service, self.key_path(service))
        elif force and existed:
            logger.info("auth %s: rotating key", service)
        self.keys.ensure_key(service, force=force, title=self.key_title(service))
        if not existed or force:
            logger.info("auth %s: created %s", service, self.key_path(service))

    def _announce_key(self, service: str, base_host: str, parsed: SshGitUrl) -> None:
        self._instructions.announce(
            service,
            host=base_host,
            parsed=parsed,
            pubkey=self.pub_path(service).read_text(encoding="utf-8").strip(),
            title=self.key_title(service),
        )

    def list_services(self) -> list[str]:
        return self.keys.list_services()

    def key_title(self, service: str) -> str:
        return f"raft:{service}@{HostGateway().hostname()}"

    def show_pubkey(self, service: str) -> str:
        path = self.pub_path(service)
        if not path.is_file():
            raise OperatorError(
                f"no deploy key for {service!r}; run: raft auth setup {service}",
                has_fix=False,
            )
        return path.read_text(encoding="utf-8").strip()

    def show(self, service: str, *, repo: Optional[str] = None) -> None:
        repo_url = self.resolve_repo_url(service, repo)
        pubkey = self.show_pubkey(service)
        parsed = self.urls.parse(repo_url)
        host = self.urls.real_git_host(service, parsed.host)
        self._instructions.print_for_copy(
            service,
            host=host,
            repo_path=parsed.path,
            pubkey=pubkey,
            title=self.key_title(service),
        )

    def rewrite_clone_url(self, service: str, repo: str) -> str:
        return self._clones.rewrite(service, repo)

    def clone_urls_for_repo(self, repo: str) -> tuple[str, ...]:
        return self._clones.candidates(repo)

    def test(
        self,
        service: str,
        *,
        quiet: bool = False,
        repo: Optional[str] = None,
    ) -> None:
        repo_url = self.resolve_repo_url(service, repo)
        if not self.is_configured(service):
            raise OperatorError(
                f"no key for {service!r}; run: raft auth setup {service} --repo {repo_url}",
                has_fix=False,
            )
        url = self.rewrite_clone_url(service, repo_url)
        logger.info("auth test %s: git ls-remote %s", service, url)
        self._assert_ls_remote(service, repo_url, url)
        if not quiet:
            OperatorSay.say(f"auth test {service}: ok", style="ok")
        else:
            logger.info("auth test %s: ok", service)

    def _assert_ls_remote(self, service: str, repo_url: str, url: str) -> None:
        result = self.sh.git("ls-remote", url, "HEAD", check=False, capture=True)
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout or "").strip()
        exc = subprocess.CalledProcessError(
            result.returncode,
            ["git", "ls-remote", url, "HEAD"],
            stderr=detail,
        )
        CheckedCommands.raise_for_git_failure(exc, repo_url, app=service, always=True)

    def remove(self, service: str, *, remove_files: bool = True) -> None:
        self.keys.remove_ssh_config(service)
        if remove_files:
            self.keys.remove_key_files(service)
        suffix = " and key files" if remove_files else ""
        OperatorSay.say(f"auth {service}: removed local SSH config{suffix}", style="ok")
        OperatorSay.say(
            "if a deploy key was added on the git host, delete it there manually "
            "(GitHub → repo Settings → Deploy keys).",
            style="info",
        )

    @staticmethod
    def _pubkey_for_paste(pubkey: str) -> str:
        return DeployKeyInstructions.pubkey_for_paste(pubkey)
