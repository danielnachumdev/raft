"""Flock for serve notification channel writes to ``settings.yaml``."""

from pathlib import Path
from typing import Optional

from .settings_lock import SettingsLock


class NotificationsLock(SettingsLock):
    """Alias of :class:`SettingsLock` (same ``settings.lock`` flock)."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(root, timeout=timeout)
