"""HttpProbe (urllib mocked)."""

import urllib.error
from unittest.mock import MagicMock, patch

from .base import AdapterTestCase
from raft.adapters import HttpProbe


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
