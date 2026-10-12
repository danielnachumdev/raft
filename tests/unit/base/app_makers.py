"""In-memory App factories for unit tests."""

from typing import Optional

from raft.core.core.models.app import App


class AppMakers:
    @classmethod
    def make_app(
        cls,
        name: str = "app",
        *,
        public_host: Optional[str] = None,
        source: str = "local",
        path: Optional[str] = None,
        repo: Optional[str] = None,
        ref: str = "main",
        image: Optional[str] = None,
        group: Optional[str] = None,
    ) -> App:
        return App(
            name=name,
            public_host=public_host or f"{name}.test",
            source=source,
            path=path or f"apps/{name}",
            repo=repo,
            ref=ref,
            image=image,
            group=group,
        )

    @classmethod
    def make_git_app(
        cls,
        name: str = "svc",
        *,
        repo: str = "git@github.com:org/svc.git",
        public_host: str = "svc.test",
        path: Optional[str] = None,
        ref: str = "main",
    ) -> App:
        return cls.make_app(
            name,
            public_host=public_host,
            source="git",
            path=path or f"apps/{name}",
            repo=repo,
            ref=ref,
        )
