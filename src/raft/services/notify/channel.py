"""Runtime channel descriptor for dispatcher input (from settings via adapter)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ChannelDescriptor:
    """One configured channel: type discriminator + opaque settings blob."""

    channel_id: str
    type_id: str
    enabled: bool = True
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))
