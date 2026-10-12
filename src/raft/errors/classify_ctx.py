"""Context carried into subprocess failure classification."""

from dataclasses import dataclass
from typing import Any, Optional, Sequence

__all__ = ["SubprocessCtx"]


@dataclass(frozen=True)
class SubprocessCtx:
    app: Optional[str] = None
    repo: Optional[str] = None
    stack: Any = None
    action: str = ""
    missing_certs: Optional[Sequence[Any]] = None
