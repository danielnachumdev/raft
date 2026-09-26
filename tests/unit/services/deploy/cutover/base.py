"""Shared CutoverSession test case."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.services.deploy.cutover import CutoverSession

from ....base import make_app, make_stack, write_applied_app
from ...base import ServicesTestCase


class CutoverTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _cutover_setup(self, _services_setup) -> None:
        self.session = self.cutover_session()

    def docker_session(self, *, ref_text: str | None = None) -> CutoverSession:
        write_applied_app(
            self.tmp_path,
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            public_host="hub.test",
            build_context=None,
        )
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        stack = make_stack(self.tmp_path, (app,), drain_seconds=0.0, ready_timeout_seconds=1.0)
        if ref_text is not None:
            (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
            (self.tmp_path / "deploy" / "hub.ref").write_text(ref_text, encoding="utf-8")
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        return CutoverSession(
            stack=stack, app=app, docker=docker, nginx=MagicMock(), http=MagicMock()
        )
