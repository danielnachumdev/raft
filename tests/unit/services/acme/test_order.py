"""AcmeOrderRunner with a fake ClientV2."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from acme import challenges, errors

from raft.services.acme.order import AcmeOrderRunner

from ...base import RaftTestCase


def _http01_order(token_byte: bytes = b"t") -> tuple[MagicMock, MagicMock, str]:
    chall = challenges.HTTP01(token=token_byte * 32)
    token = chall.encode("token")
    challb = MagicMock()
    challb.chall = chall
    challb.response_and_validation.return_value = (MagicMock(), "key-auth-value")
    authz = MagicMock()
    authz.body.challenges = [challb]
    order = MagicMock()
    order.authorizations = [authz]
    return order, challb, token


class TestAcmeOrderRunner(RaftTestCase):
    def test_issue_writes_and_cleans_webroot(self) -> None:
        order, _challb, token = _http01_order()
        finalized = MagicMock()
        finalized.fullchain_pem = "-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n"
        client = MagicMock()
        client.net.key = MagicMock()
        client.new_order.return_value = order
        client.poll_and_finalize.return_value = finalized
        pem = AcmeOrderRunner(self.tmp_path, client_factory=lambda: client).issue(b"csr")
        assert b"BEGIN CERTIFICATE" in pem
        client.answer_challenge.assert_called_once()
        assert not (self.tmp_path / "state" / "acme" / "http-01" / token).is_file()

    def test_missing_http01_raises(self) -> None:
        authz = MagicMock()
        authz.body.challenges = []
        order = MagicMock()
        order.authorizations = [authz]
        client = MagicMock()
        client.new_order.return_value = order
        with pytest.raises(errors.Error, match="HTTP-01"):
            AcmeOrderRunner(self.tmp_path, client_factory=lambda: client).issue(b"csr")

    def test_empty_fullchain_raises(self) -> None:
        order, _c, _t = _http01_order(b"u")
        client = MagicMock()
        client.new_order.return_value = order
        client.poll_and_finalize.return_value = SimpleNamespace(fullchain_pem=None)
        with pytest.raises(errors.Error, match="fullchain"):
            AcmeOrderRunner(self.tmp_path, client_factory=lambda: client).issue(b"csr")
