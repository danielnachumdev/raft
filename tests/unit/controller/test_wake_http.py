"""Wake HTTP API for gate activity/wake callbacks."""

from __future__ import annotations

from unittest.mock import MagicMock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from raft.controller.wake_http import start_wake_http, _parse_path


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
        urlopen(f"http://127.0.0.1:{port}/activity/web", timeout=2)
        req = Request(f"http://127.0.0.1:{port}/wake/web", method="POST")
        urlopen(req, timeout=2)
        scaler.record_activity.assert_called_once_with("web")
        scaler.request_wake.assert_called_once_with("web")
        try:
            urlopen(f"http://127.0.0.1:{port}/missing", timeout=2)
        except HTTPError as exc:
            assert exc.code == 404
        server.stop()
        server.stop()
