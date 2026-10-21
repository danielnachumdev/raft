"""Host-targeted ``docker run`` one-shot (sync Update / detached Redeploy)."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.shell import Shell

from .host_oneshot_ids import HostOneshotIds
from .host_oneshot_mounts import HostOneshotDockerMounts

logger = logging.getLogger(__name__)


class HostOneshot:
    """Run or detach a command as the host user with ``HOME`` bind-mounted."""

    def __init__(
        self,
        shell: Shell,
        *,
        host_home: Optional[str] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        docker_gid: Optional[int] = None,
        image: Optional[str] = None,
    ) -> None:
        self._shell = shell
        self._ids = HostOneshotIds(
            host_home=host_home,
            uid=uid,
            gid=gid,
            docker_gid=docker_gid,
            image=image,
        )

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        with_docker: bool = False,
    ) -> None:
        cmd = self.docker_argv(argv, with_docker=with_docker, detach=False)
        logger.info(
            "host oneshot run home=%s user=%s:%s image=%s docker=%s cmd=%s",
            self._ids.host_home,
            self._ids.uid,
            self._ids.gid,
            self._ids.image,
            with_docker,
            list(argv),
        )
        try:
            self._shell.run(cmd, timeout=timeout, capture=True)
        except Exception as exc:
            raise OperatorError(self._failure_message(exc)) from exc
        logger.info("host oneshot finished home=%s", self._ids.host_home)

    def start(self, argv: Sequence[str], *, with_docker: bool = True) -> str:
        """Detach (``docker run -d``); return container id. Job outlives caller."""
        cmd = self.docker_argv(argv, with_docker=with_docker, detach=True)
        logger.info(
            "host oneshot start home=%s user=%s:%s image=%s docker=%s cmd=%s",
            self._ids.host_home,
            self._ids.uid,
            self._ids.gid,
            self._ids.image,
            with_docker,
            list(argv),
        )
        try:
            completed = self._shell.run(cmd, timeout=60.0, capture=True)
        except Exception as exc:
            raise OperatorError(self._failure_message(exc)) from exc
        job_id = self._parse_container_id(completed.stdout)
        logger.info("host oneshot detached id=%s", job_id)
        return job_id

    @staticmethod
    def _parse_container_id(stdout: object) -> str:
        text = stdout if isinstance(stdout, str) else ""
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        if not lines:
            raise OperatorError(
                "host Docker one-shot started but returned no container id.\n"
                "Fix: check Docker, then retry from the dashboard or run "
                "the command on the host."
            )
        return lines[-1]

    def docker_argv(
        self,
        argv: Sequence[str],
        *,
        with_docker: bool,
        detach: bool,
    ) -> List[str]:
        return [
            *self._docker_prefix(with_docker=with_docker, detach=detach),
            self._ids.image,
            *argv,
        ]

    def _docker_prefix(self, *, with_docker: bool, detach: bool) -> List[str]:
        prefix = ["docker", "run"]
        if detach:
            prefix.append("-d")
        prefix.append("--rm")
        prefix.extend(self._user_home_flags())
        if with_docker:
            prefix.extend(HostOneshotDockerMounts(self._ids.docker_gid).flags())
        return prefix

    def _user_home_flags(self) -> List[str]:
        home = self._ids.host_home
        return [
            "--user",
            f"{self._ids.uid}:{self._ids.gid}",
            "-e",
            f"HOME={home}",
            "-e",
            f"PATH={self._ids.path_env}",
            "-v",
            f"{home}:{home}",
            "-w",
            home,
        ]

    @staticmethod
    def _failure_message(exc: BaseException) -> str:
        detail = str(exc).strip()
        stderr = getattr(exc, "stderr", None)
        if isinstance(stderr, str) and stderr.strip():
            detail = stderr.strip()
        elif getattr(exc, "output", None):
            out = getattr(exc, "output", "")
            if isinstance(out, str) and out.strip():
                detail = out.strip()
        tail = detail.splitlines()[-1] if detail else "unknown error"
        return (
            "host Docker one-shot failed: "
            f"{tail}\n"
            "Fix: check Docker, RAFT_HOST_HOME, and outbound network, "
            "then retry from the dashboard or run the command on the host"
        )
