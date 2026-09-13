"""Per-service read-only SSH deploy keys for private git sources."""

from __future__ import annotations

import logging
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models.app import App
from ..models.stack import Stack
from ..adapters.shell import Shell
from ..ui import say

logger = logging.getLogger(__name__)

_BEGIN = "# BEGIN raft:{name}"
_END = "# END raft:{name}"
_SSH_GIT_RE = re.compile(
    r"^(?:ssh://)?(?:git@)?(?P<host>[^/:]+)[:/](?P<path>.+?)(?:\.git)?/?$"
)

@dataclass(frozen=True)
class SshGitUrl:
    host: str
    path: str

    @property
    def canonical(self) -> str:
        return f"git@{self.host}:{self.path}.git"

    def with_host_alias(self, alias: str) -> str:
        return f"git@{alias}:{self.path}.git"

def parse_ssh_git_url(url: str) -> SshGitUrl:
    raw = url.strip()
    if raw.startswith("https://") or raw.startswith("http://"):
        raise ValueError(
            f"HTTPS remotes are not managed by raft auth ({url!r}); "
            "use an SSH URL like git@github.com:owner/repo.git"
        )
    match = _SSH_GIT_RE.match(raw)
    if not match:
        raise ValueError(f"cannot parse SSH git URL: {url!r}")
    host = match.group("host")
    path = match.group("path").strip("/")
    if not path or "/" not in path:
        raise ValueError(f"SSH git URL must include owner/repo: {url!r}")
    return SshGitUrl(host=host, path=path)

def default_ssh_dir() -> Path:
    override = os.environ.get("RAFT_SSH_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".ssh").resolve()

def host_alias(service: str, git_host: str) -> str:
    marker = f"-raft-{service}"
    if git_host.endswith(marker):
        return git_host
    return f"{git_host}-raft-{service}"

def real_git_host(service: str, git_host: str) -> str:
    marker = f"-raft-{service}"
    if git_host.endswith(marker):
        return git_host[: -len(marker)] or git_host
    return git_host

class GitAuthManager:
    def __init__(
        self,
        stack: Stack,
        shell: Optional[Shell] = None,
        *,
        ssh_dir: Optional[Path] = None,
    ) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)
        self.ssh_dir = ssh_dir or default_ssh_dir()
        self.keys_dir = self.ssh_dir / "raft"
        self.config_path = self.ssh_dir / "config"

    def key_path(self, service: str) -> Path:
        return self.keys_dir / f"{service}_ed25519"

    def pub_path(self, service: str) -> Path:
        return Path(str(self.key_path(service)) + ".pub")

    def is_configured(self, service: str) -> bool:
        return self.key_path(service).is_file() and self.pub_path(service).is_file()

    def effective_clone_url(self, app: App) -> str:
        if not app.repo:
            raise ValueError(f"service {app.name!r} has no repo URL")
        if not self.is_configured(app.name):
            return app.repo
        parsed = parse_ssh_git_url(app.repo)
        base_host = real_git_host(app.name, parsed.host)
        alias = host_alias(app.name, base_host)
        return parsed.with_host_alias(alias)

    def setup(
        self,
        service: str,
        *,
        force: bool = False,
    ) -> None:
        app = self.stack.app(service)
        if not app.repo:
            raise RuntimeError(
                f"{service!r} needs a repo URL in the applied App manifest "
                f"(git source, or docker with repo for checkout)"
            )
        parsed = parse_ssh_git_url(app.repo)
        base_host = real_git_host(service, parsed.host)
        alias = host_alias(service, base_host)

        self._ensure_ssh_layout()
        if self.is_configured(service) and not force:
            logger.info("auth %s: key already exists (%s)", service, self.key_path(service))
        else:
            if force and self.is_configured(service):
                logger.info("auth %s: rotating key", service)
                self.key_path(service).unlink(missing_ok=True)
                self.pub_path(service).unlink(missing_ok=True)
            self._generate_key(service)
            logger.info("auth %s: created %s", service, self.key_path(service))

        self._upsert_ssh_config(service, alias=alias, hostname=base_host)
        logger.info("auth %s: SSH Host %s → %s", service, alias, base_host)

        pubkey = self.pub_path(service).read_text(encoding="utf-8").strip()
        title = self.key_title(service)
        self._print_deploy_key_for_copy(
            service,
            host=base_host,
            repo_path=parsed.path,
            pubkey=pubkey,
            title=title,
        )

        logger.info("auth %s: clone URL will be %s", service, parsed.with_host_alias(alias))
        say(f"next: raft auth test {service} && raft sync {service}")

    def list_services(self) -> list[str]:
        if not self.keys_dir.is_dir():
            return []
        names: list[str] = []
        for pub in sorted(self.keys_dir.glob("*_ed25519.pub")):
            name = pub.name[: -len("_ed25519.pub")]
            if self.key_path(name).is_file():
                names.append(name)
        return names

    def key_title(self, service: str) -> str:
        return f"raft:{service}@{socket.gethostname()}"

    def show_pubkey(self, service: str) -> str:
        path = self.pub_path(service)
        if not path.is_file():
            raise RuntimeError(
                f"no deploy key for {service!r}; run: raft auth setup {service}"
            )
        return path.read_text(encoding="utf-8").strip()

    def show(self, service: str) -> None:
        app = self.stack.app(service)
        if not app.repo:
            raise RuntimeError(
                f"{service!r} needs a repo URL in the applied App manifest "
                f"(git source, or docker with repo for checkout)"
            )
        pubkey = self.show_pubkey(service)
        parsed = parse_ssh_git_url(app.repo)
        host = real_git_host(service, parsed.host)
        self._print_deploy_key_for_copy(
            service,
            host=host,
            repo_path=parsed.path,
            pubkey=pubkey,
            title=self.key_title(service),
        )

    def test(self, service: str, *, quiet: bool = False) -> None:
        app = self.stack.app(service)
        if not app.repo:
            raise RuntimeError(
                f"{service!r} has no repo URL in inventory (needed for deploy-key auth)"
            )
        if not self.is_configured(service):
            raise RuntimeError(
                f"no key for {service!r}; run: raft auth setup {service}"
            )
        url = self.effective_clone_url(app)
        logger.info("auth test %s: git ls-remote %s", service, url)
        result = self.sh.git("ls-remote", url, "HEAD", check=False, capture=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"auth test failed for {service!r}"
                + (f":\n{detail}" if detail else "")
            )
        if not quiet:
            say(f"auth test {service}: ok")
        else:
            logger.info("auth test %s: ok", service)

    def remove(self, service: str, *, remove_files: bool = True) -> None:
        self._remove_ssh_config(service)
        if remove_files:
            self.key_path(service).unlink(missing_ok=True)
            self.pub_path(service).unlink(missing_ok=True)
        suffix = " and key files" if remove_files else ""
        say(f"auth {service}: removed local SSH config{suffix}")
        say(
            "if a deploy key was added on the git host, delete it there manually "
            "(GitHub → repo Settings → Deploy keys)."
        )

    def _ensure_ssh_layout(self) -> None:
        self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.ssh_dir, 0o700)
        self.keys_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.keys_dir, 0o700)
        if not self.config_path.exists():
            self.config_path.touch(mode=0o600)
        os.chmod(self.config_path, 0o600)

    def _generate_key(self, service: str) -> None:
        comment = self.key_title(service)
        self.sh.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(self.key_path(service)),
                "-N",
                "",
                "-C",
                comment,
                "-q",
            ],
            capture=True,
        )
        os.chmod(self.key_path(service), 0o600)
        os.chmod(self.pub_path(service), 0o644)

    def _upsert_ssh_config(self, service: str, *, alias: str, hostname: str) -> None:
        self._ensure_ssh_layout()
        block = "\n".join(
            [
                _BEGIN.format(name=service),
                f"Host {alias}",
                f"  HostName {hostname}",
                "  User git",
                f"  IdentityFile {self.key_path(service)}",
                "  IdentitiesOnly yes",
                _END.format(name=service),
                "",
            ]
        )
        text = self.config_path.read_text(encoding="utf-8")
        text = self._strip_block(text, service)
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        self.config_path.write_text(text + block, encoding="utf-8")
        os.chmod(self.config_path, 0o600)

    def _remove_ssh_config(self, service: str) -> None:
        if not self.config_path.is_file():
            return
        text = self._strip_block(self.config_path.read_text(encoding="utf-8"), service)
        self.config_path.write_text(text, encoding="utf-8")
        os.chmod(self.config_path, 0o600)

    @staticmethod
    def _strip_block(text: str, service: str) -> str:
        begin = _BEGIN.format(name=service)
        end = _END.format(name=service)
        pattern = re.compile(
            re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
            re.DOTALL,
        )
        return pattern.sub("", text)

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
        say(f"Add a read-only deploy key for {service}:")
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
