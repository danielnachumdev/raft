"""AcmeHttp01Webroot token file helpers."""

from __future__ import annotations

import pytest

from raft.services.acme.webroot import AcmeHttp01Webroot

from ...base import RaftTestCase


class TestAcmeHttp01Webroot(RaftTestCase):
    def test_write_and_delete(self) -> None:
        web = AcmeHttp01Webroot(self.tmp_path)
        path = web.write("tok123", "key-auth")
        assert path.read_text(encoding="utf-8") == "key-auth"
        assert path.parent.name == "http-01"
        web.delete("tok123")
        assert not path.is_file()
        web.delete("tok123")  # missing is fine

    def test_rejects_traversal_token(self) -> None:
        web = AcmeHttp01Webroot(self.tmp_path)
        with pytest.raises(ValueError, match="invalid"):
            web.write("../escape", "x")
