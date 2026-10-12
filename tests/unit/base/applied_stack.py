"""Applied app + local stack + shell: shared arrange for domain/adapter tests."""

from unittest.mock import MagicMock

import pytest

from .applied_inventory import AppliedInventory
from .raft_test_case import RaftTestCase
from .stack_makers import StackMakers


class AppliedStackCase(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _applied_stack(self, _raft_base) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "app")
        self.stack = StackMakers.make_local_stack(self.tmp_path, drain_seconds=0.0)
        self.app = self.stack.apps[0]
        self.shell = MagicMock()
