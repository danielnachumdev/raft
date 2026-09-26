"""HttpProbe (urllib mocked) and TCP listener checks."""

import urllib.error
from unittest.mock import MagicMock, patch

from raft.adapters import HttpProbe
from raft.adapters.http import _NoRedirect
from raft.models import App

from .base import AdapterTestCase


class TestHttpProbe(AdapterTestCase):
    def test_no_redirect_handler_suppresses_follow(self) -> None:
        assert (
            _NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "http://example/"
            )
            is None
        )
    def _response(self, status: int) -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_public_host_ok_true(self) -> None:
        probe = HttpProbe(self.stack)
        with patch.object(probe, "_opener") as opener:
            opener.open.return_value = self._response(200)
            assert probe.public_host_ok(self.app) is True

    def test_public_host_ok_accepts_oauth_redirect_without_following(self) -> None:
        """Dev oauth2 gate returns 302; following off-box yields 404 and false negatives."""
        probe = HttpProbe(self.stack)
        with patch.object(probe, "_opener") as opener:
            opener.open.side_effect = urllib.error.HTTPError(
                url="http://127.0.0.1/",
                code=302,
                msg="Found",
                hdrs=MagicMock(),
                fp=None,
            )
            assert probe.public_host_ok(self.app) is True

    def test_public_host_ok_false_on_status(self) -> None:
        probe = HttpProbe(self.stack)
        with patch.object(probe, "_opener") as opener:
            opener.open.return_value = self._response(500)
            assert probe.public_host_ok(self.app) is False

    def test_public_host_ok_false_on_http_error_4xx(self) -> None:
        probe = HttpProbe(self.stack)
        with patch.object(probe, "_opener") as opener:
            opener.open.side_effect = urllib.error.HTTPError(
                url="http://127.0.0.1/",
                code=404,
                msg="Not Found",
                hdrs=MagicMock(),
                fp=None,
            )
            assert probe.public_host_ok(self.app) is False

    def test_public_host_ok_false_on_error(self) -> None:
        probe = HttpProbe(self.stack)
        with patch.object(probe, "_opener") as opener:
            opener.open.side_effect = urllib.error.URLError("down")
            assert probe.public_host_ok(self.app) is False

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
