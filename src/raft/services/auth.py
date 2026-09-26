"""Per-service read-only SSH deploy keys for private git sources."""

from __future__ import annotations

import logging
import socket
import subprocess
from typing import Optional

from raft.errors import OperatorError, raise_for_git_failure

from ..adapters.shell import Shell
from ..models.app import App
from ..models.stack import Stack
from ..ui import say
from .auth_ssh import SshDeployKeys
from .auth_urls import host_alias, parse_ssh_git_url, real_git_host

logger = logging.getLogger(__name__)


class GitAuthManager:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.keys = SshDeployKeys(Shell(stack.root))

    @property
    def sh(self) -> Shell:
        return self.keys.sh

    @sh.setter
    def sh(self, value: Shell) -> None:
        self.keys.sh = value

    @property
    def ssh_dir(self):
        return self.keys.ssh_dir

    @ssh_dir.setter
    def ssh_dir(self, value) -> None:
        self.keys.ssh_dir = value

    @property
    def keys_dir(self):
        return self.keys.keys_dir

    @keys_dir.setter
    def keys_dir(self, value) -> None:
        self.keys.keys_dir = value

    @property
    def config_path(self):
        return self.keys.config_path

    @config_path.setter
    def config_path(self, value) -> None:
        self.keys.config_path = value

    def key_path(self, service: str):
        return self.keys.key_path(service)

    def pub_path(self, service: str):
        return self.keys.pub_path(service)

    def is_configured(self, service: str) -> bool:
        return self.keys.is_configured(service)

    def effective_clone_url(self, app: App) -> str:
        if not app.repo:
            raise ValueError(f"service {app.name!r} has no repo URL")
        if not self.is_configured(app.name):
            return app.repo
        parsed = parse_ssh_git_url(app.repo)
        base_host = real_git_host(app.name, parsed.host)
        alias = host_alias(app.name, base_host)
        return parsed.with_host_alias(alias)

    def resolve_repo_url(self, service: str, repo: Optional[str] = None) -> str:
        """Repo URL from ``--repo`` or an already-applied App (no chicken-and-egg)."""
        if repo is not None and str(repo).strip():
            return str(repo).strip()
        try:
            app = self.stack.app(service)
        except RuntimeError as exc:
            known = ", ".join(a.name for a in self.stack.apps) or "(none applied)"
            raise OperatorError(
                f"unknown app {service!r} (known: {known}). "
                f"Pass --repo git@host:owner/repo.git to set up auth before apply, "
                f"or register a manifest first: raft apply --file PATH --no-deploy",
                has_fix=False,
            ) from exc
        if not app.repo:
            raise OperatorError(
                f"{service!r} needs a repo URL: pass --repo, or set spec.repo on the "
                f"applied App (git source, or docker with repo for checkout)",
                has_fix=False,
            )
        return app.repo

    def setup(
        self,
        service: str,
        *,
        force: bool = False,
        repo: Optional[str] = None,
    ) -> None:
        repo_url = self.resolve_repo_url(service, repo)
        parsed = parse_ssh_git_url(repo_url)
        base_host = real_git_host(service, parsed.host)
        alias = host_alias(service, base_host)
        self.keys.ensure_layout()
        self._prepare_key(service, force=force)
        self.keys.upsert_ssh_config(service, alias=alias, hostname=base_host)
        logger.info("auth %s: SSH Host %s → %s", service, alias, base_host)
        self._announce_key(service, base_host, parsed)
        logger.info(
            "auth %s: clone URL will be %s", service, parsed.with_host_alias(alias)
        )
        self._say_auth_next_steps(service, repo_url)

    def _prepare_key(self, service: str, *, force: bool) -> None:
        existed = self.is_configured(service)
        if existed and not force:
            logger.info("auth %s: key already exists (%s)", service, self.key_path(service))
        elif force and existed:
            logger.info("auth %s: rotating key", service)
        self.keys.ensure_key(service, force=force, title=self.key_title(service))
        if not existed or force:
            logger.info("auth %s: created %s", service, self.key_path(service))

    def _announce_key(self, service: str, base_host: str, parsed) -> None:
        self._print_deploy_key_for_copy(
            service,
            host=base_host,
            repo_path=parsed.path,
            pubkey=self.pub_path(service).read_text(encoding="utf-8").strip(),
            title=self.key_title(service),
        )

    def _say_auth_next_steps(self, service: str, repo_url: str) -> None:
        applied = any(a.name == service for a in self.stack.apps)
        if applied:
            say(f"next: raft auth test {service} && raft sync {service}", style="info")
        else:
            say(
                f"next: raft auth test {service} --repo {repo_url} "
                f"&& raft apply --git {repo_url}",
                style="info",
            )

    def list_services(self) -> list[str]:
        return self.keys.list_services()

    def key_title(self, service: str) -> str:
        return f"raft:{service}@{socket.gethostname()}"

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
        parsed = parse_ssh_git_url(repo_url)
        host = real_git_host(service, parsed.host)
        self._print_deploy_key_for_copy(
            service,
            host=host,
            repo_path=parsed.path,
            pubkey=pubkey,
            title=self.key_title(service),
        )

    def rewrite_clone_url(self, service: str, repo: str) -> str:
        """Map a canonical SSH URL onto this service's Host alias when configured."""
        if not self.is_configured(service):
            return repo
        parsed = parse_ssh_git_url(repo)
        base_host = real_git_host(service, parsed.host)
        alias = host_alias(service, base_host)
        return parsed.with_host_alias(alias)

    def clone_urls_for_repo(self, repo: str) -> tuple[str, ...]:
        """Candidate clone URLs: configured Host aliases first, then the raw repo.

        Trying aliases before ``git@github.com:…`` avoids noisy ``Permission denied
        (publickey)`` on the default identity when a deploy key is already set up.
        """
        try:
            parsed = parse_ssh_git_url(repo)
        except ValueError:
            return (repo,)
        urls: list[str] = []
        for service in self.list_services():
            base_host = real_git_host(service, parsed.host)
            alias = host_alias(service, base_host)
            urls.append(parsed.with_host_alias(alias))
        urls.append(repo)
        return tuple(dict.fromkeys(urls))

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
            say(f"auth test {service}: ok", style="ok")
        else:
            logger.info("auth test %s: ok", service)

    def _assert_ls_remote(self, service: str, repo_url: str, url: str) -> None:
        result = self.sh.git("ls-remote", url, "HEAD", check=False, capture=True)
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout or "").strip()
        exc = subprocess.CalledProcessError(
            result.returncode, ["git", "ls-remote", url, "HEAD"], stderr=detail,
        )
        raise_for_git_failure(exc, repo_url, app=service, always=True)

    def remove(self, service: str, *, remove_files: bool = True) -> None:
        self.keys.remove_ssh_config(service)
        if remove_files:
            self.keys.remove_key_files(service)
        suffix = " and key files" if remove_files else ""
        say(f"auth {service}: removed local SSH config{suffix}", style="ok")
        say(
            "if a deploy key was added on the git host, delete it there manually "
            "(GitHub → repo Settings → Deploy keys).",
            style="info",
        )

    @staticmethod
    def _pubkey_for_paste(pubkey: str) -> str:
        parts = pubkey.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return pubkey

    def _print_deploy_key_for_copy(
        self,
        service: str,
        *,
        host: str,
        repo_path: str,
        pubkey: str,
        title: str,
    ) -> None:
        say(f"Add a read-only deploy key for {service}:", style="info")
        say("")
        say(f"  Title:  {title}")
        say(f"  Key:    {self._pubkey_for_paste(pubkey)}")
        say("")
        if host == "github.com":
            say(f"  Open:   https://github.com/{repo_path}/settings/keys/new")
            say("          (paste Title + Key, enable Allow read-only access)")
        else:
            say(f"  Open:   {host} → {repo_path} → Deploy keys → Add")
            say("          (paste Title + Key as read-only)")
