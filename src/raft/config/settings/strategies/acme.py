"""Parse ``acme:`` from settings.yaml."""

from typing import Any

from ....errors.cta import OperatorError
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser
from ..types import (
    DEFAULT_ACME_CHALLENGE,
    DEFAULT_ACME_DIRECTORY,
    DEFAULT_ACME_RENEW_DAYS_BEFORE_EXPIRY,
    AcmeConfig,
)


class AcmeSettingsParser(SettingsSectionParser[AcmeConfig]):
    """Validate and build :class:`AcmeConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> AcmeConfig:
        if raw is None:
            return AcmeConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml acme must be a mapping.\n"
                "Fix: set acme: {email: ops@example.com, ...} in ~/.raft/settings.yaml"
            )
        return AcmeConfig(
            email=self._scalars.optional_str(raw.get("email")),
            directory=self._directory(raw.get("directory")),
            renew_days_before_expiry=self._scalars.pos_int(
                raw,
                "renewDaysBeforeExpiry",
                DEFAULT_ACME_RENEW_DAYS_BEFORE_EXPIRY,
                "acme",
            ),
            challenge=self._challenge(raw.get("challenge")),
        )

    @staticmethod
    def _directory(raw: Any) -> str:
        if raw is None:
            return DEFAULT_ACME_DIRECTORY
        text = str(raw).strip()
        if not text:
            raise OperatorError(
                "settings.yaml acme.directory must be a non-empty URL.\n"
                "Fix: set acme.directory in ~/.raft/settings.yaml "
                f"(default {DEFAULT_ACME_DIRECTORY})"
            )
        return text

    @staticmethod
    def _challenge(raw: Any) -> str:
        if raw is None:
            return DEFAULT_ACME_CHALLENGE
        text = str(raw).strip().lower() or DEFAULT_ACME_CHALLENGE
        if text != DEFAULT_ACME_CHALLENGE:
            raise OperatorError(
                f"settings.yaml acme.challenge must be {DEFAULT_ACME_CHALLENGE!r} "
                f"(v1), got {text!r}.\n"
                f"Fix: set acme.challenge: {DEFAULT_ACME_CHALLENGE} "
                f"or omit the key in ~/.raft/settings.yaml"
            )
        return text
