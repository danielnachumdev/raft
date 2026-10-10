"""Cutover wait / abort coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.deploy.cutover import CutoverSession

from tests.unit.base import make_app, make_local_stack, make_stack, write_applied_app
from tests.unit.cta_asserts import assert_logged, assert_operator
from .base import CutoverTestCase


class TestCutoverWait(CutoverTestCase):
    def test_wait_ready_invokes_compose_ready_for_expose_none(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="",
            source="docker",
            image="redis",
            build_context=None,
            extra=self._expose_none_extra(),
        )
        app = make_app("app", source="docker", image="redis", public_host="")
        docker = MagicMock()
        docker.service_is_ready.return_value = True
        session = self._cutover_session(app, docker)
        with patch("raft.deploy.cutover.time.sleep"):
            session._wait_ready("compose ready")
        docker.service_is_ready.assert_called_with(app.compose_id)

    @staticmethod
    def _expose_none_extra() -> dict:
        return {
            "ports": [{"name": "http", "containerPort": 8000, "expose": "none"}],
            "readiness": {"type": "tcp", "port": "http"},
        }

    def _cutover_session(self, app, docker) -> CutoverSession:
        return CutoverSession(
            stack=make_stack(self.tmp_path, (app,), drain_seconds=0.0),
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )

    def test_wait_ready_uses_app_readiness_timeout(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "http", "port": "http", "timeoutSeconds": 90}},
        )
        stack = make_local_stack(self.tmp_path, drain_seconds=0.0, ready_timeout_seconds=1.0)
        s = CutoverSession(
            stack=stack,
            app=stack.apps[0],
            docker=MagicMock(),
            nginx=MagicMock(),
            http=MagicMock(),
        )
        s.http.public_host_ok.return_value = False
        with patch("raft.deploy.cutover.WaitUntil") as wait:
            s._wait_ready("slow ready")
        assert wait.call_args.kwargs["timeout"] == 90.0
        assert "timeoutSeconds=90s" in wait.call_args.kwargs["fix"]

    def _clock_patches(self, step: float):
        clock = {"t": 0.0}

        def mono() -> float:
            return clock["t"]

        def sleep(_seconds: float) -> None:
            clock["t"] += step

        return (
            patch("raft.deploy.wait.time.sleep", side_effect=sleep),
            patch("raft.deploy.wait.time.monotonic", side_effect=mono),
        )

    def test_wait_until_reports_budget_and_diagnostics(self, caplog) -> None:
        from raft.errors.cta import OperatorError
        from raft.deploy.wait import WaitUntil

        sleep_p, mono_p = self._clock_patches(0.02)
        with caplog.at_level("ERROR"), sleep_p, mono_p:
            with pytest.raises(OperatorError) as exc:
                self._wait_until_budget()
        assert_operator(
            exc.value,
            contains=("demo ready", "running/starting"),
            fix_label="Fix: raise readiness.timeoutSeconds",
        )
        assert_logged(caplog, level="ERROR", contains=("demo ready",))

    @staticmethod
    def _wait_until_budget() -> None:
        from raft.deploy.wait import WaitUntil

        WaitUntil(
            "demo ready",
            lambda: False,
            timeout=0.01,
            interval=0.01,
            progress_every=0,
            fix="raise readiness.timeoutSeconds",
            diagnostics=lambda: "--- svc (running/starting) ---",
        ).run()

    def test_wait_until_logs_progress(self, caplog) -> None:
        from raft.errors.cta import OperatorError
        from raft.deploy.wait import WaitUntil

        sleep_p, mono_p = self._clock_patches(0.1)
        with caplog.at_level("INFO"), sleep_p, mono_p:
            with pytest.raises(OperatorError) as caught:
                WaitUntil(
                    "slow ready",
                    lambda: False,
                    timeout=0.25,
                    interval=0.05,
                    progress_every=0.1,
                ).run()
        assert_operator(caught.value, has_fix=False, contains=("slow ready",))
        assert_logged(caplog, level="INFO", contains=("slow ready",))

    def test_abort_cleanup_restores_stable_and_removes_tmp(self) -> None:
        s = self.session
        s.tmp_active = True
        s.abort_cleanup()
        s.nginx.point_at.assert_called_once_with(s.app, s.app.compose_id)
        s.docker.nginx_test_and_reload.assert_called_once()
        s.docker.remove_container.assert_called_once_with(s.app.tmp_container)
        assert s.tmp_active is False

    def test_abort_cleanup_swallows_restore_and_remove_errors(self, caplog) -> None:

        s = self.session
        s.tmp_active = True
        s.nginx.point_at.side_effect = RuntimeError("nginx down")
        s.docker.remove_container.side_effect = RuntimeError("rm failed")
        with caplog.at_level("WARNING"):
            s.abort_cleanup()
        assert_logged(caplog, level="WARNING", contains=(s.app.compose_id,))
        assert_logged(caplog, level="WARNING", contains=(s.app.tmp_container,))
        assert s.tmp_active is True

    def test_abort_cleanup_noop_when_tmp_inactive(self) -> None:
        s = self.session
        s.tmp_active = False
        s.abort_cleanup()
        s.nginx.point_at.assert_not_called()
        s.docker.remove_container.assert_not_called()

    def test_wait_ready_skips_when_readiness_none(self) -> None:
        write_applied_app(self.tmp_path, "app", extra={"readiness": {"type": "none"}})
        with patch("raft.deploy.cutover.WaitUntil") as wait:
            self.session._wait_ready("noop")
        wait.assert_not_called()

    def test_log_prints(self, caplog) -> None:

        with caplog.at_level("INFO"):
            self.session.log("hello")
        assert_logged(caplog, level="INFO", contains=("hello",))
