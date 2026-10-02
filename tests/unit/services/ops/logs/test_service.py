"""Unit tests for ``Logs.show`` wiring (snapshot + mocked follow)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

from raft.errors import OperatorError
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

    def test_follow_streams_via_adapter(self) -> None:
        logs = self._logs()
        with patch.object(logs.docker, "try_service_container_id", return_value="cid"):
            with patch.object(logs.docker, "follow_compose_logs") as follow:
                logs.show("gate", follow=True, tail=50)
        follow.assert_called_once_with("raft-gate", tail=50)

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
