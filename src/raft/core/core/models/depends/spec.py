"""One ``dependsOn`` edge entry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DependsOnSpec:
    """Compose/wake/heal use ``name``; idle co-stop uses ``scale_with_parent``."""

    name: str
    scale_with_parent: bool = True
