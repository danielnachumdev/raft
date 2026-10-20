"""HttpProbe (gateway mocked) and TCP listener checks."""

from unittest.mock import MagicMock, patch

from raft.core.platform.adapters import HttpProbe
from raft.core.platform.adapters.http.gateway import HttpGateway, _NoRedirect
from raft.core.platform.adapters.http.tcp import TcpGateway
from raft.core.core.models.app import App

from tests.unit.core.platform.adapters.base import AdapterTestCase


class TestHttpProbe(AdapterTestCase):
    def test_no_redirect_handler_suppresses_follow(self) -> None:
        assert (
            _NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://example/") is None
        )

    def test_public_host_ok_true(self) -> None:
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 200
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app) is True
        http.get.assert_called_once_with(
            "http://127.0.0.1/",
            headers={"Host": self.app.public_host},
        )

    def test_public_host_ok_uses_readiness_path(self) -> None:
        """Compose healthchecks use readiness.path; Host wait must hit the same URL."""
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 200
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app, path="/health") is True
        http.get.assert_called_once_with(
            "http://127.0.0.1/health",
            headers={"Host": self.app.public_host},
        )

    def test_public_host_ok_accepts_oauth_static_202(self) -> None:
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 202
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app, path="/") is True

    def test_public_host_ok_accepts_oauth_redirect_without_following(self) -> None:
        """Dev oauth2 gate returns 302; following off-box yields 404 and false negatives."""
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 302
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app) is True

    def test_public_host_ok_false_on_status(self) -> None:
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 500
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app) is False

    def test_public_host_ok_false_on_http_error_4xx(self) -> None:
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = 404
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app) is False

    def test_public_host_ok_false_on_error(self) -> None:
        http = MagicMock(spec=HttpGateway)
        http.get.return_value = None
        assert HttpProbe(self.stack, http=http).public_host_ok(self.app) is False

    def test_public_host_ok_empty_host(self) -> None:
        app = App(name="x", public_host="", source="local", path="services/x/checkout")
        assert HttpProbe(self.stack).public_host_ok(app) is True

    def test_tcp_port_ok(self) -> None:
        tcp = MagicMock(spec=TcpGateway)
        tcp.connect.return_value = True
        assert HttpProbe(self.stack, tcp=tcp).tcp_port_ok(25) is True
        tcp.connect.assert_called_once_with("127.0.0.1", 25)
        tcp.connect.return_value = False
        assert HttpProbe(self.stack, tcp=tcp).tcp_port_ok(25) is False

    def test_tcp_gateway_uses_socket(self) -> None:
        with patch(
            "raft.core.platform.adapters.http.tcp.socket.create_connection",
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock()),
                __exit__=MagicMock(return_value=False),
            ),
        ):
            assert TcpGateway().connect("127.0.0.1", 25) is True
        with patch(
            "raft.core.platform.adapters.http.tcp.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            assert TcpGateway().connect("127.0.0.1", 25) is False
