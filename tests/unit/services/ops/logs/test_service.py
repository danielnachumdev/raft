"""Unit tests for ``Logs.show`` / ``snapshot`` / ``follow`` wiring."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

from raft.errors.cta import OperatorError
from raft.services.ops.logs import Logs

from ....base import RaftTestCase, make_app, make_stack


class TestLogsShow(RaftTestCase):
    def _logs(self) -> Logs:
        return Logs(make_stack(self.tmp_path, (make_app("app"),)))

    def test_snapshot_prints_compose_logs(self) -> None:
        logs = self._logs()
        out = StringIO()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(
                logs.docker, "compose_logs", return_value="line1\nline2"
            ) as compose:
                logs.show("app", tail=20, out=out)
        compose.assert_called_once_with("app", tail=20)
        assert out.getvalue() == "line1\nline2\n"

    def test_follow_prints_shared_iterator(self) -> None:
        logs = self._logs()
        out = StringIO()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(
                logs.docker,
                "iter_follow_compose_logs",
                return_value=iter(["a", "b"]),
            ) as follow:
                logs.show("gate", follow=True, tail=50, out=out)
        follow.assert_called_once_with("raft-gate", tail=50)
        assert out.getvalue() == "a\nb\n"

    def test_follow_yields_shared_iterator(self) -> None:
        logs = self._logs()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(
                logs.docker,
                "iter_follow_compose_logs",
                return_value=iter(["x"]),
            ) as follow:
                assert list(logs.follow("app", tail=10)) == ["x"]
        follow.assert_called_once_with("app", tail=10)

    def test_follow_swallows_keyboard_interrupt(self) -> None:
        logs = self._logs()

        def boom(*_a, **_k):
            yield "one"
            raise KeyboardInterrupt

        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(logs.docker, "iter_follow_compose_logs", side_effect=boom):
                logs.show("app", follow=True, out=StringIO())

    def test_missing_container_raises(self) -> None:
        logs = self._logs()
        with patch.object(logs.docker, "try_service_container_id", return_value=None):
            with pytest.raises(OperatorError, match="is not running"):
                logs.show("app")

    def test_empty_snapshot_prints_nothing(self) -> None:
        logs = self._logs()
        out = StringIO()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(logs.docker, "compose_logs", return_value=""):
                logs.show("app", out=out)
        assert out.getvalue() == ""

    def test_snapshot_returns_compose_logs_text(self) -> None:
        logs = self._logs()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(
                logs.docker, "compose_logs", return_value="line1\nline2"
            ) as compose:
                text = logs.snapshot("app", tail=20)
        compose.assert_called_once_with("app", tail=20)
        assert text == "line1\nline2"

    def test_snapshot_empty_returns_empty_string(self) -> None:
        logs = self._logs()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(logs.docker, "compose_logs", return_value=""):
                assert logs.snapshot("app") == ""
