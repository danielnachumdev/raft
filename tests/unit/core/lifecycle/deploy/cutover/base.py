"""Shared CutoverSession test case."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import pytest

from raft.core.lifecycle.deploy.cutover import CutoverSession

from tests.unit.base import AppMakers, AppliedInventory, StackMakers
from tests.unit.domain_case import DomainTestCase


class CutoverTestCase(DomainTestCase):
    @pytest.fixture(autouse=True)
    def _cutover_setup(self, _applied_stack) -> None:
        self.session = self.cutover_session()

    def docker_session(self, *, ref_text: Optional[str] = None) -> CutoverSession:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            public_host="hub.test",
            build_context=None,
        )
        app = AppMakers.make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        stack = StackMakers.make_stack(self.tmp_path, (app,), drain_seconds=0.0, ready_timeout_seconds=1.0)
        if ref_text is not None:
            (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
            (self.tmp_path / "deploy" / "hub.ref").write_text(ref_text, encoding="utf-8")
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        return CutoverSession(
            stack=stack, app=app, docker=docker, nginx=MagicMock(), http=MagicMock()
        )
