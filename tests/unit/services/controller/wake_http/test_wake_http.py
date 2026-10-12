"""Wake HTTP API for gate activity/wake callbacks."""

from unittest.mock import MagicMock

from raft.services.controller.wake_http import WakeHttpPath, WakeHttpServer
from tests.shared.http import HttpClient


class TestWakeHttp:
    def test_parse_path(self) -> None:
        parse = WakeHttpPath().parse
        assert parse("/activity/web") == ("activity", "web")
        assert parse("/wake/web") == ("wake", "web")
        assert parse("/nope") == (None, None)
        assert parse("/other/web") == (None, None)

    def test_start_and_handle(self) -> None:
        scaler = MagicMock()
        server = WakeHttpServer.bind(scaler, host="127.0.0.1", port=0)
        assert server._httpd is not None
        port = server._httpd.server_address[1]
        client = HttpClient(f"http://127.0.0.1:{port}", timeout=2)
        client.get("/activity/web", expect_status=204)
        client.post("/wake/web", expect_status=202)
        scaler.record_activity.assert_called_once_with("web")
        scaler.request_wake.assert_called_once_with("web")
        client.get("/missing", expect_status=404)
        server.stop()
        server.stop()
