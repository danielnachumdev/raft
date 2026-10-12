"""Lock wait budget from override arg or ``RAFT_LOCK_TIMEOUT_SECONDS``."""

import os
from typing import Optional

from ..errors.domain import DomainErrors

ENV_LOCK_TIMEOUT = "RAFT_LOCK_TIMEOUT_SECONDS"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300.0


class LockTimeout:
    """Seconds to wait for a busy lock before ``OperatorError``."""

    ENV_NAME = ENV_LOCK_TIMEOUT
    DEFAULT_SECONDS = DEFAULT_LOCK_TIMEOUT_SECONDS

    @classmethod
    def resolve(cls, override: Optional[float] = None) -> float:
        if override is not None:
            return cls._from_override(override)
        return cls._from_env()

    @classmethod
    def _from_override(cls, override: float) -> float:
        if override < 0:
            raise DomainErrors.invalid_lock_timeout(repr(override))
        return float(override)

    @classmethod
    def _from_env(cls) -> float:
        raw = os.environ.get(cls.ENV_NAME)
        if raw is None or not str(raw).strip():
            return cls.DEFAULT_SECONDS
        return cls._parse_env(raw)

    @classmethod
    def _parse_env(cls, raw: str) -> float:
        try:
            value = float(str(raw).strip())
        except ValueError as exc:
            raise DomainErrors.invalid_lock_timeout(raw) from exc
        if value < 0:
            raise DomainErrors.invalid_lock_timeout(raw)
        return value
