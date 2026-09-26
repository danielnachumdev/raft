"""Shared SourceSync test case."""

from __future__ import annotations

import pytest

from raft.services.sync import SourceSync

from ...base import make_git_app, make_stack
from ..base import ServicesTestCase


class SyncTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _sync_setup(self, _services_setup) -> None:
        self.syncer = SourceSync(self.stack, self.shell)

    def git_syncer(self, **app_kwargs) -> SourceSync:
        app = make_git_app(**app_kwargs)
        self.stack = make_stack(self.tmp_path, (app,))
        self.app = app
        self.syncer = SourceSync(self.stack, self.shell)
        return self.syncer

    def ensure_git_checkout(self) -> None:
        dest = self.app.abs_path(self.tmp_path)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ".git").mkdir(exist_ok=True)
