"""One Compose service row from batch ``ps`` output."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ComposeServiceRow:
    """One Compose service row from batch ``ps`` output."""

    service: str
    state: str
    health: str
