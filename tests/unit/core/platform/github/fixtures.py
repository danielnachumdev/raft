"""Shared fixtures for serve GitHub unit tests."""

import time
from pathlib import Path
from typing import List, Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.manifest import CONTRACT_REL_PATH
from raft.core.platform.github.accounts import GithubAccount
from raft.core.platform.github.providers import GithubProvider, GithubRepo, filter_repos


def sample_repo(**kwargs) -> GithubRepo:
    base = dict(
        full_name="o/r",
        name="r",
        owner="o",
        private=True,
        default_branch="main",
        clone_url="c",
        ssh_url="git@github.com:o/r.git",
        html_url="https://github.com/o/r",
    )
    base.update(kwargs)
    return GithubRepo(**base)


def sample_account(**kwargs) -> GithubAccount:
    base = dict(
        id="acct-1",
        access_token="t",
        login="u",
        expires_at=time.time() + 60,
    )
    base.update(kwargs)
    return GithubAccount(**base)


def stub_auth(auth_cls) -> None:
    auth = auth_cls.return_value
    auth.show_pubkey.return_value = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI comment"
    )
    auth_cls._pubkey_for_paste.return_value = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI"
    )


class StubLocalGithubProvider(GithubProvider):
    """Test-only provider backed by a local tree (replaces removed product mock)."""

    def __init__(self, root: Path, *, full_name: str = "demo/site") -> None:
        self._root = root
        self._full_name = full_name
        owner, name = full_name.split("/", 1)
        self._repo = GithubRepo(
            full_name=full_name,
            name=name,
            owner=owner,
            private=False,
            default_branch="main",
            clone_url=f"https://github.com/{full_name}.git",
            ssh_url=f"git@github.com:{full_name}.git",
            html_url=f"https://github.com/{full_name}",
        )

    def list_repos(self, token: str, *, query: str = "") -> List[GithubRepo]:
        del token
        return filter_repos([self._repo], query)

    def fetch_manifest(self, token: str, full_name: str, ref: str) -> str:
        del token, ref
        tree = self.resolve_local_tree(full_name)
        if tree is None:
            raise OperatorError(
                f"unknown repo {full_name!r}\nFix: pick a listed repo",
                has_fix=False,
            )
        path = tree / CONTRACT_REL_PATH
        if not path.is_file():
            raise OperatorError(
                f"no {CONTRACT_REL_PATH.as_posix()} in {full_name}\n"
                f"Fix: add that file on the default branch",
                has_fix=False,
            )
        return path.read_text(encoding="utf-8")

    def resolve_local_tree(self, full_name: str) -> Optional[Path]:
        if full_name != self._full_name:
            return None
        return self._root if self._root.is_dir() else None


def write_local_app_tree(root: Path, *, name: str = "site") -> Path:
    """Create a minimal App tree under ``root`` for deploy-runner tests."""
    root.mkdir(parents=True, exist_ok=True)
    raft = root / ".raft"
    raft.mkdir(parents=True, exist_ok=True)
    (raft / "app.yaml").write_text(
        "apiVersion: raft/v1\n"
        "kind: App\n"
        f"metadata:\n  name: {name}\n"
        "spec:\n"
        "  publicHost: site.example.com\n"
        "  tls: off\n"
        "  source: local\n"
        f"  path: apps/{name}\n"
        "  build:\n    context: .\n"
        "  ports:\n"
        "    - name: http\n"
        "      containerPort: 80\n"
        "      expose: http\n"
        "  readiness:\n"
        "    type: none\n"
        "    port: http\n"
        "    path: /\n",
        encoding="utf-8",
    )
    return root
