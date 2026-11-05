"""Named RBAC role with permission grants."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class RbacRole:
    """Named role with a permission grant list."""

    id: str
    permissions: Tuple[str, ...]
