"""Invocation-scoped trace ids via ContextVar."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar, Token
from typing import Optional

_current_tid: ContextVar[Optional[str]] = ContextVar("trace_tid", default=None)
logger = logging.getLogger(__name__)


class TraceContext:
    """Scoped UUID correlator for logs. Nest with an explicit parent tid for branches."""

    def __init__(self, parent_tid: Optional[str] = None) -> None:
        self._parent_tid = parent_tid
        self._tid: Optional[str] = None
        self._token: Optional[Token] = None

    def __enter__(self) -> str:
        self._tid = str(uuid.uuid4())
        self._log_branch_if_nested()
        self._token = _current_tid.set(self._tid)
        return self._tid

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            _current_tid.reset(self._token)
            self._token = None
        return None

    def _log_branch_if_nested(self) -> None:
        if self._parent_tid is None:
            return
        logger.debug(
            "trace branch parent=%s child=%s",
            self._parent_tid,
            self._tid,
        )

    @classmethod
    def current(cls) -> Optional[str]:
        return _current_tid.get()
