"""SSH git URL parsing and Host-alias helpers for raft auth."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_SSH_GIT_RE = re.compile(r"^(?:ssh://)?(?:git@)?(?P<host>[^/:]+)[:/](?P<path>.+?)(?:\.git)?/?$")


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
