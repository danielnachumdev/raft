"""One ACME account key + registration per data home + directory URL."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

import josepy as jose
from acme import client, messages
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .paths import AcmePaths

logger = logging.getLogger(__name__)

_ACCOUNT_LOCK = threading.Lock()
_USER_AGENT = "raft-acme/0.1"


class AcmeAccountStore:
    """Load or register the shared Let's Encrypt (ACME) account."""

    def __init__(self, data_home: Path) -> None:
        self._paths = AcmePaths(data_home)

    def client_for(self, *, directory_url: str, email: str) -> client.ClientV2:
        """Return a ClientV2 bound to the on-disk account for ``directory_url``."""
        with _ACCOUNT_LOCK:
            return self._client_unlocked(directory_url=directory_url, email=email)

    def _client_unlocked(self, *, directory_url: str, email: str) -> client.ClientV2:
        self._paths.ensure_dirs()
        key = self._load_or_create_key()
        net = client.ClientNetwork(key, user_agent=_USER_AGENT)
        directory = client.ClientV2.get_directory(directory_url, net)
        acme_client = client.ClientV2(directory, net)
        regr = self._load_registration(directory_url)
        if regr is not None:
            net.account = regr
            return acme_client
        regr = self._register(acme_client, email=email, directory_url=directory_url)
        net.account = regr
        return acme_client

    def _load_or_create_key(self) -> jose.JWKRSA:
        self._paths.ensure_dirs()
        path = self._paths.account_key
        if path.is_file():
            raw = path.read_bytes()
            loaded = serialization.load_pem_private_key(raw, password=None)
            return jose.JWKRSA(key=loaded)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        logger.info("created ACME account key at %s", path)
        return jose.JWKRSA(key=key)

    def _load_registration(self, directory_url: str) -> Optional[messages.RegistrationResource]:
        path = self._paths.account_json
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        if data.get("directory") != directory_url:
            logger.info("ACME directory changed; will register a new account")
            return None
        return self._registration_from_mapping(data)

    @staticmethod
    def _registration_from_mapping(data: dict[str, Any]) -> Optional[messages.RegistrationResource]:
        uri = data.get("uri")
        body = data.get("body")
        if not uri or not isinstance(body, dict):
            return None
        try:
            return messages.RegistrationResource(
                body=messages.Registration.from_json(body),
                uri=str(uri),
            )
        except Exception:  # noqa: BLE001 — corrupt account.json → re-register
            return None

    def _register(
        self,
        acme_client: client.ClientV2,
        *,
        email: str,
        directory_url: str,
    ) -> messages.RegistrationResource:
        new_reg = messages.NewRegistration.from_data(
            email=email,
            terms_of_service_agreed=True,
        )
        regr = acme_client.new_account(new_reg)
        self._persist_registration(regr, directory_url=directory_url)
        logger.info("registered ACME account for %s", email)
        return regr

    def _persist_registration(
        self,
        regr: messages.RegistrationResource,
        *,
        directory_url: str,
    ) -> None:
        payload = {
            "directory": directory_url,
            "uri": regr.uri,
            "body": regr.body.to_json(),
        }
        self._paths.account_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
