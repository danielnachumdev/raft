"""In-memory Stack factories for unit tests."""

from pathlib import Path
from typing import Optional, Sequence

from raft.models.app import App
from raft.models.stack import Stack

from .app_makers import AppMakers


class StackMakers(AppMakers):
    @classmethod
    def make_stack(
        cls,
        root: Path,
        apps: Optional[Sequence[App]] = None,
        **kwargs,
    ) -> Stack:
        if apps is None:
            apps = (cls.make_app(),)
        return Stack(root=root, apps=tuple(apps), **kwargs)

    @classmethod
    def make_local_stack(cls, root: Path, *names: str, **kwargs) -> Stack:
        names = names or ("app",)
        return cls.make_stack(root, tuple(cls.make_app(n) for n in names), **kwargs)

    @classmethod
    def make_git_stack(
        cls,
        root: Path,
        *,
        repo: str = "git@github.com:org/svc.git",
        with_local: bool = True,
    ) -> Stack:
        apps = [cls.make_git_app(repo=repo)]
        if with_local:
            apps.append(cls.make_app("localapp", public_host="local.test"))
        return cls.make_stack(root, apps)
