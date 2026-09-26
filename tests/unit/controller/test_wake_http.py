"""Wake HTTP API for gate activity/wake callbacks."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.controller.wake_http import start_wake_http, _parse_path

from tests.shared.http import HttpClient


class TestWakeHttp:
    def test_parse_path(self) -> None:
        assert _parse_path("/activity/web") == ("activity", "web")
        assert _parse_path("/wake/web") == ("wake", "web")
        assert _parse_path("/nope") == (None, None)
        assert _parse_path("/other/web") == (None, None)

    def test_start_and_handle(self) -> None:
        scaler = MagicMock()
        server = start_wake_http(scaler, host="127.0.0.1", port=0)
        assert server._httpd is not None
        port = server._httpd.server_address[1]
        client = HttpClient(f"http://127.0.0.1:{port}", timeout=2)
        client.get("/activity/web")
        client.post("/wake/web")
        scaler.record_activity.assert_called_once_with("web")
        scaler.request_wake.assert_called_once_with("web")
        status, _ = client.get("/missing")
        assert status == 404
        server.stop()
        server.stop()
