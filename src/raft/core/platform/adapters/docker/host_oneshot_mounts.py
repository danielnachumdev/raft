"""Volume / group flags when a host one-shot needs the Docker Engine.

``docker run -v`` sources are always **host** paths (Docker API). Never use
``shutil.which`` from inside ``raft-dashboard`` — that returns the in-image
CLI path and creates an empty host directory when bind-mounted.
"""

from __future__ import annotations

import os
from typing import List

_DOCKER_SOCK = "/var/run/docker.sock"
_BIN_ENV = "RAFT_HOST_DOCKER_BIN"
_PLUGIN_ENV = "RAFT_HOST_DOCKER_PLUGIN_DIR"
_DEFAULT_BIN = "/usr/bin/docker"
_DEFAULT_PLUGIN = "/usr/libexec/docker/cli-plugins"


class HostOneshotDockerMounts:
    """Bind-mount docker.sock + host docker CLI (+ compose plugins)."""

    def __init__(self, docker_gid: int) -> None:
        self._docker_gid = docker_gid

    def flags(self) -> List[str]:
        out = [
            "--group-add",
            str(self._docker_gid),
            "-v",
            f"{_DOCKER_SOCK}:{_DOCKER_SOCK}",
        ]
        out.extend(self._docker_bin_mount())
        out.extend(self._plugin_mount())
        return out

    @staticmethod
    def _docker_bin_mount() -> List[str]:
        path = (os.environ.get(_BIN_ENV) or "").strip() or _DEFAULT_BIN
        return ["-v", f"{path}:/usr/bin/docker:ro"]

    @staticmethod
    def _plugin_mount() -> List[str]:
        path = (os.environ.get(_PLUGIN_ENV) or "").strip() or _DEFAULT_PLUGIN
        return ["-v", f"{path}:{path}:ro"]
