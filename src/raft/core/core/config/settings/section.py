"""ABC for settings.yaml section parsers."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SettingsSectionParser(ABC, Generic[T]):
    """Parse one top-level settings.yaml section into a typed config object."""

    @abstractmethod
    def parse(self, raw: Any) -> T:
        """Build the section config; ``None`` means omit / defaults."""
