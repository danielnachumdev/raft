"""Resolve host uid/gid/home/image for Docker one-shots."""

from __future__ import annotations

import os
from typing import Optional

from .host_oneshot_image import DEFAULT_HOST_ONESHOT_IMAGE

_HOST_HOME_ENV = "RAFT_HOST_HOME"
_HOST_UID_ENV = "RAFT_HOST_UID"
_HOST_GID_ENV = "RAFT_HOST_GID"
_DOCKER_GID_ENV = "RAFT_DOCKER_GID"
_IMAGE_ENV = "RAFT_HOST_UPDATE_IMAGE"
_DOCKER_SOCK = "/var/run/docker.sock"


class HostOneshotIds:
    """HOME / UID / GID / docker GID / image for ``HostOneshot``."""

    def __init__(
        self,
        *,
        host_home: Optional[str] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
        docker_gid: Optional[int] = None,
        image: Optional[str] = None,
    ) -> None:
        self.host_home = (host_home or os.environ.get(_HOST_HOME_ENV) or "").strip()
        self.uid = self._resolve_id(uid, _HOST_UID_ENV, os.getuid)
        self.gid = self._resolve_id(gid, _HOST_GID_ENV, os.getgid)
        self.docker_gid = self._resolve_docker_gid(docker_gid)
        self.image = self._resolve_image(image)

    @property
    def path_env(self) -> str:
        home = self.host_home
        return (
            f"{home}/.local/bin:/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        )

    @staticmethod
    def _resolve_id(explicit: Optional[int], env_name: str, fallback) -> int:
        if explicit is not None:
            return explicit
        raw = (os.environ.get(env_name) or "").strip()
        if raw.isdigit():
            return int(raw)
        return int(fallback())

    @classmethod
    def _resolve_docker_gid(cls, explicit: Optional[int]) -> int:
        if explicit is not None:
            return explicit
        raw = (os.environ.get(_DOCKER_GID_ENV) or "").strip()
        if raw.isdigit():
            return int(raw)
        try:
            return int(os.stat(_DOCKER_SOCK).st_gid)
        except OSError:
            return 0

    @staticmethod
    def _resolve_image(image: Optional[str]) -> str:
        if image:
            return image
        return (os.environ.get(_IMAGE_ENV) or "").strip() or DEFAULT_HOST_ONESHOT_IMAGE
