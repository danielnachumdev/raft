"""Host-targeted ``install.sh`` via a one-shot container (dashboard apply)."""

from __future__ import annotations

import os
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.shell import Shell
from .install_cmd import DEFAULT_HOST_UPDATE_IMAGE, InstallCmd

_HOST_HOME_ENV = "RAFT_HOST_HOME"
_IMAGE_ENV = "RAFT_HOST_UPDATE_IMAGE"
_TIMEOUT_SECONDS = 600.0


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
    ) -> None:
        self._shell = shell
        self._host_home = (host_home or os.environ.get(_HOST_HOME_ENV) or "").strip()
        self._uid = os.getuid() if uid is None else uid
        self._gid = os.getgid() if gid is None else gid
        self._image = self._resolve_image(image)

    def run(self, url: str, ref: Optional[str]) -> None:
        try:
            self._shell.run(
                self.argv(url, ref), timeout=_TIMEOUT_SECONDS, capture=True
            )
        except Exception as exc:
            raise OperatorError(self._failure_message(exc)) from exc

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
            "raft update failed (host Docker one-shot could not run "
            f"install.sh): {tail}\n"
            "Fix: check Docker, outbound HTTPS, and RAFT_HOST_HOME, "
            "then retry Settings → Update or run `raft update` on the host"
        )

    def argv(self, url: str, ref: Optional[str]) -> list[str]:
        return [
            *self._docker_prefix(),
            self._image,
            "bash",
            "-c",
            InstallCmd.pipeline_script(ref),
            "_",
            url,
        ]

    def _docker_prefix(self) -> list[str]:
        home = self._host_home
        path = (
            f"{home}/.local/bin:/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        )
        return [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{self._uid}:{self._gid}",
            "-e",
            f"HOME={home}",
            "-e",
            f"PATH={path}",
            "-v",
            f"{home}:{home}",
            "-w",
            home,
        ]

    @staticmethod
    def _resolve_image(image: Optional[str]) -> str:
        if image:
            return image
        return (os.environ.get(_IMAGE_ENV) or "").strip() or DEFAULT_HOST_UPDATE_IMAGE
