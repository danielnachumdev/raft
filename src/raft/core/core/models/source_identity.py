"""Durable App source identity for name-ownership checks on apply."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

from raft.core.core.errors.domain import DomainErrors

from .app import App

__all__ = ["AppSourceIdentity"]


@dataclass(frozen=True)
class AppSourceIdentity:
    """Comparable source key: kind + durable locator (not checkout paths / refs)."""

    source: str
    key: str

    def label(self) -> str:
        if self.source == "git":
            return f"git repo={self.key}"
        if self.source == "docker":
            return f"docker image={self.key}"
        return f"local path={self.key}"

    @classmethod
    def from_app(cls, app: App) -> "AppSourceIdentity":
        if app.source == "git":
            return cls("git", cls._normalize_git_repo(app.repo or ""))
        if app.source == "docker":
            return cls("docker", (app.image or "").strip().lower())
        return cls("local", cls._normalize_local_path(app.path))

    @classmethod
    def reject_takeover(cls, existing: App, incoming: App) -> None:
        owned = cls.from_app(existing)
        next_id = cls.from_app(incoming)
        if owned == next_id:
            return
        raise DomainErrors.app_name_source_conflict(
            incoming.name,
            existing=owned.label(),
            incoming=next_id.label(),
        )

    @staticmethod
    def _normalize_local_path(path: str) -> str:
        raw = path.strip().replace("\\", "/")
        parts: list[str] = []
        for part in PurePosixPath(raw).parts:
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/".join(parts) if parts else "."

    @classmethod
    def _normalize_git_repo(cls, repo: str) -> str:
        raw = repo.strip()
        if not raw:
            return ""
        if cls._is_scp_style(raw):
            user_host, path = raw.split(":", 1)
            host = user_host.rsplit("@", 1)[-1]
            return cls._canon_host_path(host, path)
        parsed = urlparse(raw if "://" in raw else f"ssh://{raw}")
        host = parsed.hostname or ""
        return cls._canon_host_path(host, parsed.path)

    @staticmethod
    def _is_scp_style(raw: str) -> bool:
        return "://" not in raw and "@" in raw and ":" in raw.split("@", 1)[-1]

    @staticmethod
    def _canon_host_path(host: str, path: str) -> str:
        cleaned = path.strip().lstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[: -len(".git")]
        return f"{host.strip().lower()}/{cleaned}".lower().strip("/")
