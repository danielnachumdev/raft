"""Host-targeted ``install.sh`` via shared ``HostOneshot`` (dashboard apply)."""

from __future__ import annotations

import logging
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.update_proxy_timeout import (
    UPDATE_PROXY_TIMEOUT_SECONDS,
)
from raft.core.platform.adapters.docker import HostOneshot
from raft.core.platform.adapters.shell import Shell
from .install_cmd import InstallCmd

_TIMEOUT_SECONDS = float(UPDATE_PROXY_TIMEOUT_SECONDS)
logger = logging.getLogger(__name__)


class HostDockerUpdate:
    """Run ``install.sh`` as the host user with ``HOME`` bind-mounted."""

    def __init__(
        self,
        shell: Shell,
        *,
        host_home: Optional[str] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        image: Optional[str] = None,
        oneshot: Optional[HostOneshot] = None,
    ) -> None:
        self._oneshot = oneshot or HostOneshot(
            shell, host_home=host_home, uid=uid, gid=gid, image=image
        )

    def run(self, url: str, ref: Optional[str]) -> None:
        logger.info(
            "host docker update start ref=%s",
            (ref or "").strip() or "(latest)",
        )
        try:
            self._oneshot.run(
                self._inner_argv(url, ref),
                timeout=_TIMEOUT_SECONDS,
                with_docker=False,
            )
        except OperatorError as exc:
            logger.error("host docker update failed: %s", exc)
            raise OperatorError(self._wrap_failure(str(exc))) from exc
        logger.info("host docker update finished")

    def argv(self, url: str, ref: Optional[str]) -> list[str]:
        """Full ``docker run …`` argv (tests + introspection)."""
        return self._oneshot.docker_argv(
            self._inner_argv(url, ref),
            with_docker=False,
            detach=False,
        )

    @staticmethod
    def _inner_argv(url: str, ref: Optional[str]) -> list[str]:
        return [
            "bash",
            "-c",
            InstallCmd.pipeline_script(ref),
            "_",
            url,
        ]

    @staticmethod
    def _wrap_failure(detail: str) -> str:
        first = detail.splitlines()[0] if detail else "unknown error"
        prefix = "host Docker one-shot failed: "
        tail = first[len(prefix) :] if first.startswith(prefix) else first
        return (
            "raft update failed (host Docker one-shot could not run "
            f"install.sh): {tail}\n"
            "Fix: check Docker, outbound HTTPS, and RAFT_HOST_HOME, "
            "then retry Settings → Update or run `raft update` on the host"
        )
