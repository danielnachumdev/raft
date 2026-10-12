"""Registry load issue and batch result types."""

from dataclasses import dataclass

from .app import App


@dataclass(frozen=True)
class RegistryIssue:
    """One applied manifest that failed to load (others still load)."""

    file: str
    error: str

    def to_dict(self) -> dict[str, str]:
        return {"file": self.file, "error": self.error}


@dataclass(frozen=True)
class RegistryLoadResult:
    apps: tuple[App, ...]
    issues: tuple[RegistryIssue, ...]
