"""Volume / group flags when a host one-shot needs the Docker Engine."""

from __future__ import annotations

import os
import shutil
from typing import List

_DOCKER_SOCK = "/var/run/docker.sock"
_PLUGIN_DIRS = (
    "/usr/libexec/docker/cli-plugins",
    "/usr/local/lib/docker/cli-plugins",
)


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
        out.extend(self._plugin_mounts())
        return out

    @staticmethod
    def _docker_bin_mount() -> List[str]:
        path = shutil.which("docker")
        if not path or not os.path.isfile(path):
            return []
        return ["-v", f"{path}:/usr/bin/docker:ro"]

    @staticmethod
    def _plugin_mounts() -> List[str]:
        out: List[str] = []
        for plugin_dir in _PLUGIN_DIRS:
            if os.path.isdir(plugin_dir):
                out.extend(["-v", f"{plugin_dir}:{plugin_dir}:ro"])
        return out
