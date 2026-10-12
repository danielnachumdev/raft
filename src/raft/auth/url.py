"""Parsed SSH git remote (host + owner/repo path)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SshGitUrl:
    host: str
    path: str

    @property
    def canonical(self) -> str:
        return f"git@{self.host}:{self.path}.git"

    def with_host_alias(self, alias: str) -> str:
        return f"git@{alias}:{self.path}.git"
