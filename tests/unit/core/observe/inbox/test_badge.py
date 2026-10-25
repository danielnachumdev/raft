"""InboxBadge formatting and +99 overflow."""

from raft.core.observe.inbox import BADGE_OVERFLOW, InboxBadge
from tests.unit.base import RaftTestCase


class TestInboxBadge(RaftTestCase):
    def test_format_and_cap(self) -> None:
        assert InboxBadge.format(0) is None
        assert InboxBadge.format(-3) is None
        assert InboxBadge.format(1) == "1"
        assert InboxBadge.format(99) == "99"
        assert InboxBadge.format(100) == BADGE_OVERFLOW
        assert InboxBadge.format(1000) == BADGE_OVERFLOW
        assert InboxBadge.capped(0) == 0
        assert InboxBadge.capped(50) == 50
        assert InboxBadge.capped(100) == 99
