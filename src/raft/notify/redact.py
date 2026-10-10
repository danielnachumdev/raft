"""Redact secret-like keys from notification channel settings for APIs/logs."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class SettingsRedactor:
    """Mask token/password/secret-like values; strip URL query secrets."""

    _FRAGMENTS = (
        "token",
        "password",
        "passwd",
        "secret",
        "authorization",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
    )
    _MASK = "***"

    def redact(self, settings: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self._value(key, value) for key, value in settings.items()}

    def merge_preserving_secrets(
        self,
        existing: Mapping[str, Any],
        incoming: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply ``incoming``; keep existing secrets when client sends the mask."""
        out: dict[str, Any] = {}
        for key, value in incoming.items():
            out[key] = self._merge_one(key, value, existing.get(key))
        return out

    def _merge_one(self, key: str, value: Any, prior: Any) -> Any:
        if value == self._MASK and self._key_is_secret(key) and prior not in (None, ""):
            return prior
        if isinstance(value, Mapping) and isinstance(prior, Mapping):
            return self.merge_preserving_secrets(prior, value)
        return value

    def _value(self, key: str, value: Any) -> Any:
        if self._key_is_secret(key):
            return self._present(value)
        if isinstance(value, Mapping):
            return self.redact(value)
        if isinstance(value, str) and self._looks_like_url(value):
            return self._redact_url(value)
        return value

    def _key_is_secret(self, key: str) -> bool:
        lowered = key.strip().lower().replace("-", "_")
        return any(part in lowered for part in self._FRAGMENTS)

    @staticmethod
    def _present(value: Any) -> Any:
        if value is None or value == "":
            return value
        return SettingsRedactor._MASK

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        return "://" in value and not value.startswith("://")

    def _redact_url(self, value: str) -> str:
        parts = urlsplit(value)
        if not parts.query:
            return value
        redacted = [
            (key, self._MASK if self._key_is_secret(key) else item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment)
        )
