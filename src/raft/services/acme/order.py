"""Run one ACME HTTP-01 order via the official ``acme`` ClientV2."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Sequence

from acme import challenges, client, errors, messages

from .webroot import AcmeHttp01Webroot

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], client.ClientV2]


class AcmeOrderRunner:
    """newOrder → HTTP-01 webroot → finalize → return fullchain PEM bytes."""

    def __init__(
        self,
        data_home: Path,
        *,
        client_factory: ClientFactory,
        webroot: Optional[AcmeHttp01Webroot] = None,
    ) -> None:
        self._client_factory = client_factory
        self._webroot = webroot or AcmeHttp01Webroot(data_home)

    def issue(self, csr_pem: bytes) -> bytes:
        acme_client = self._client_factory()
        order = acme_client.new_order(csr_pem)
        tokens = self._answer_http01(acme_client, order)
        try:
            finalized = acme_client.poll_and_finalize(order)
        finally:
            for token in tokens:
                self._webroot.delete(token)
        fullchain = finalized.fullchain_pem
        if not fullchain:
            raise errors.Error("ACME order finalized without fullchain PEM")
        return fullchain.encode("utf-8") if isinstance(fullchain, str) else fullchain

    def _answer_http01(
        self,
        acme_client: client.ClientV2,
        order: messages.OrderResource,
    ) -> list[str]:
        tokens: list[str] = []
        for authz in order.authorizations:
            challb = self._http01_body(authz)
            if challb is None:
                raise errors.Error("ACME authorization missing HTTP-01 challenge")
            response, validation = challb.response_and_validation(acme_client.net.key)
            token = challb.chall.encode("token")
            self._webroot.write(token, validation)
            tokens.append(token)
            acme_client.answer_challenge(challb, response)
        return tokens

    @staticmethod
    def _http01_body(authz: messages.AuthorizationResource) -> Optional[messages.ChallengeBody]:
        for challb in authz.body.challenges:
            if isinstance(challb.chall, challenges.HTTP01):
                return challb
        return None
