"""Raw ACME v2 transport over the official ``acme`` ClientV2."""

from typing import Optional

import josepy as jose
from acme import challenges, client, messages


class AcmeClientGateway:
    """Protocol-shaped calls against a bound ACME ClientV2 (no product rules)."""

    def __init__(
        self,
        acme_client: client.ClientV2,
        *,
        net: Optional[client.ClientNetwork] = None,
    ) -> None:
        self._client = acme_client
        self._net = net if net is not None else acme_client.net

    @classmethod
    def connect(
        cls,
        *,
        directory_url: str,
        key: jose.JWKRSA,
        user_agent: str,
    ) -> "AcmeClientGateway":
        net = client.ClientNetwork(key, user_agent=user_agent)
        directory = client.ClientV2.get_directory(directory_url, net)
        return cls(client.ClientV2(directory, net), net=net)

    def bind_account(self, regr: messages.RegistrationResource) -> None:
        self._net.account = regr

    def new_account(
        self,
        registration: messages.NewRegistration,
    ) -> messages.RegistrationResource:
        return self._client.new_account(registration)

    def new_order(self, csr_pem: bytes) -> messages.OrderResource:
        return self._client.new_order(csr_pem)

    def answer_challenge(
        self,
        challb: messages.ChallengeBody,
        response: challenges.ChallengeResponse,
    ) -> messages.ChallengeResource:
        return self._client.answer_challenge(challb, response)

    def poll_and_finalize(
        self,
        order: messages.OrderResource,
    ) -> messages.OrderResource:
        return self._client.poll_and_finalize(order)

    @property
    def key(self) -> jose.JWKRSA:
        return self._net.key
