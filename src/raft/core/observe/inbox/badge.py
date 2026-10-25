"""Badge counter display helpers for the operator inbox bell."""

from typing import Optional

BADGE_CAP = 99
BADGE_OVERFLOW = "+99"


class InboxBadge:
    """Format unread counts for the SPA chrome badge."""

    @staticmethod
    def format(count: int) -> Optional[str]:
        """Return badge text, or None when the badge should hide."""
        if count <= 0:
            return None
        if count > BADGE_CAP:
            return BADGE_OVERFLOW
        return str(count)

    @staticmethod
    def capped(count: int) -> int:
        """Numeric count capped at ``BADGE_CAP`` (for aria / tests)."""
        if count <= 0:
            return 0
        return min(count, BADGE_CAP)
