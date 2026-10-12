"""Run one ACME HTTP-01 order via ``AcmeClientGateway``."""

from pathlib import Path
from typing import Callable, Optional

from acme import challenges, errors, messages

from ..account import AcmeClientGateway
from ..webroot import AcmeHttp01Webroot

ClientFactory = Callable[[], AcmeClientGateway]


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
        gateway = self._client_factory()
        order = gateway.new_order(csr_pem)
        tokens = self._answer_http01(gateway, order)
        try:
            finalized = gateway.poll_and_finalize(order)
        finally:
            for token in tokens:
                self._webroot.delete(token)
        return self._fullchain_bytes(finalized)

    def _answer_http01(
        self,
        gateway: AcmeClientGateway,
        order: messages.OrderResource,
    ) -> list[str]:
        tokens: list[str] = []
        for authz in order.authorizations:
            token = self._answer_one(gateway, authz)
            if token is not None:
                tokens.append(token)
        return tokens

    def _answer_one(
        self,
        gateway: AcmeClientGateway,
        authz: messages.AuthorizationResource,
    ) -> Optional[str]:
        if self._already_valid(getattr(authz.body, "status", None)):
            return None
        challb = self._http01_body(authz)
        if challb is None:
            raise errors.Error("ACME authorization missing HTTP-01 challenge")
        if self._already_valid(getattr(challb, "status", None)):
            return None
        response, validation = challb.response_and_validation(gateway.key)
        token = challb.chall.encode("token")
        self._webroot.write(token, validation)
        gateway.answer_challenge(challb, response)
        return token

    @staticmethod
    def _fullchain_bytes(finalized: messages.OrderResource) -> bytes:
        fullchain = finalized.fullchain_pem
        if not fullchain:
            raise errors.Error("ACME order finalized without fullchain PEM")
        if isinstance(fullchain, str):
            return fullchain.encode("utf-8")
        return fullchain

    @staticmethod
    def _http01_body(
        authz: messages.AuthorizationResource,
    ) -> Optional[messages.ChallengeBody]:
        for challb in authz.body.challenges:
            if isinstance(challb.chall, challenges.HTTP01):
                return challb
        return None

    @staticmethod
    def _already_valid(status: object) -> bool:
        """True when ACME already satisfied this authz/challenge (skip re-answer)."""
        return status == messages.STATUS_VALID
