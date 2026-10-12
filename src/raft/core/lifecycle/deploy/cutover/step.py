"""One named step in a dual-run cutover plan."""

from dataclasses import dataclass
from typing import Callable

from .session import CutoverSession


@dataclass(frozen=True)
class Step:
    key: str
    summary: str
    run: Callable[[CutoverSession], None]
