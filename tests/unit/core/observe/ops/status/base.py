"""Shared Status arrange helpers for ops/status unit tests."""

from contextlib import contextmanager
from typing import Iterator, Optional, Sequence
from unittest.mock import patch

from raft.core.core.models.app import App
from raft.core.observe.ops.status import Status

from tests.unit.base import AppMakers, AppliedInventory, RaftTestCase, StackMakers

from . import fixtures as status_fx

HOST_PATCH = "raft.core.observe.ops.status.service.HostGateway.resources"


class StatusTestCase(RaftTestCase):
    def make_status(self, *names: str, apps: Optional[Sequence[App]] = None) -> Status:
        if apps is not None:
            for app in apps:
                AppliedInventory.write_applied_app(self.tmp_path, app.name)
            return Status(StackMakers.make_stack(self.tmp_path, tuple(apps)))
        names = names or ("app",)
        for name in names:
            AppliedInventory.write_applied_app(self.tmp_path, name)
        built = tuple(AppMakers.make_app(n) for n in names)
        return Status(StackMakers.make_stack(self.tmp_path, built))

    @contextmanager
    def patch_host(self) -> Iterator[None]:
        with patch(HOST_PATCH, return_value=status_fx.host()):
            yield
