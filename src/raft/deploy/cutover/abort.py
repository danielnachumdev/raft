"""Best-effort restore after a failed dual-run cutover."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import CutoverSession

logger = logging.getLogger(__name__)


class CutoverAbort:
    """Restore steady upstream and drop tmp when cutover fails mid-flight."""

    def __init__(self, session: "CutoverSession") -> None:
        self._session = session

    def run(self) -> None:
        """Idempotent. Safe when tmp was never started this session."""
        session = self._session
        if not session.tmp_active:
            return
        session.log(
            f"cutover abort cleanup: restore nginx → {session.app.compose_id}, "
            f"remove {session.app.tmp_container}"
        )
        self._restore_nginx()
        self._remove_tmp()

    def _restore_nginx(self) -> None:
        session = self._session
        try:
            session.nginx.point_at(session.app, session.app.compose_id)
            session.docker.nginx_test_and_reload()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            logger.warning(
                "abort cleanup: could not point nginx at %s",
                session.app.compose_id,
                exc_info=True,
            )

    def _remove_tmp(self) -> None:
        session = self._session
        try:
            session.docker.remove_container(session.app.tmp_container)
        except Exception:  # noqa: BLE001 — best-effort cleanup
            logger.warning(
                "abort cleanup: could not remove %s",
                session.app.tmp_container,
                exc_info=True,
            )
        else:
            session.tmp_active = False
