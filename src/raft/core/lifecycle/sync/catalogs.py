"""Shipped sync strategy catalogs (composition root)."""

from .registry import SourceSyncRegistry
from .strategies.docker import DockerSyncStrategy
from .strategies.git import GitSyncStrategy
from .strategies.local import LocalSyncStrategy


class SourceSyncCatalogs:
    """Register concrete strategies. Add sources here — do not branch in callers."""

    @staticmethod
    def default() -> SourceSyncRegistry:
        registry = SourceSyncRegistry()
        registry.register(LocalSyncStrategy())
        registry.register(GitSyncStrategy())
        registry.register(DockerSyncStrategy())
        return registry
