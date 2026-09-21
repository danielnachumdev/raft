"""HttpProbe (urllib mocked) and TCP listener checks."""

import urllib.error
from unittest.mock import MagicMock, patch

from raft.adapters import HttpProbe
from raft.models import App

from .base import AdapterTestCase


class TestHttpProbe(AdapterTestCase):
    def _response(self, status: int) -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_public_host_ok_true(self) -> None:
        with patch(
            "raft.adapters.http.urllib.request.urlopen",
            return_value=self._response(200),
        ):
            assert HttpProbe(self.stack).public_host_ok(self.app) is True

    def test_public_host_ok_false_on_status(self) -> None:
        with patch(
            "raft.adapters.http.urllib.request.urlopen",
            return_value=self._response(500),
        ):
            assert HttpProbe(self.stack).public_host_ok(self.app) is False

    def test_public_host_ok_false_on_error(self) -> None:
        with patch(
            "raft.adapters.http.urllib.request.urlopen",
            side_effect=urllib.error.URLError("down"),
        ):
            assert HttpProbe(self.stack).public_host_ok(self.app) is False

    def test_public_host_ok_empty_host(self) -> None:
        app = App(name="x", public_host="", source="local", path="apps/x")
        assert HttpProbe(self.stack).public_host_ok(app) is True

    def test_tcp_port_ok(self) -> None:
        with patch(
            "raft.adapters.http.socket.create_connection",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ):
            assert HttpProbe(self.stack).tcp_port_ok(25) is True
        with patch(
            "raft.adapters.http.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            assert HttpProbe(self.stack).tcp_port_ok(25) is False
