"""One state-machine step: next instance plus optional notify kind."""

from dataclasses import dataclass
from typing import Optional

from ..store.runtime_state import AlertInstanceState


@dataclass(frozen=True)
class Transition:
    instance: Optional[AlertInstanceState]
    notify: Optional[str]  # None | firing | resolved
