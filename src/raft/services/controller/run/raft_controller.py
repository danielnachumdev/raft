"""``raft-controller`` process entry: smoke, wake HTTP, then control loop."""

import logging
from pathlib import Path

from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.adapters.shell import Shell
from raft.core.core.config.paths import RaftHome
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import RaftConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.utils import ControllerLogging
from ..jobs import Scaler, WAKE_HTTP_PORT
from ..wake_http import WakeHttpServer
from .controller_loop import ControllerLoop
from .smoke import PrereqSmoke

logger = logging.getLogger(__name__)


class RaftController:
    """``raft-controller`` process entry: smoke, wake HTTP, then control loop."""

    def run(self) -> None:
        home = self._require_data_home()
        config = SettingsLoader().load(home)
        ControllerLogging().configure(config)
        logger.info("raft-controller starting data_home=%s", home)
        sh = Shell(home)
        PrereqSmoke(home, sh).run()
        logger.info("prereq smoke ok; entering control loop")
        self._start_loop(home, config, sh)

    def _require_data_home(self) -> Path:
        # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
        # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
        home = RaftHome().resolve()
        if not home.is_dir():
            raise OperatorError(
                f"raft data home missing: {home}\n"
                f"Fix: run `raft render` (or any raft command) on the host first"
            )
        return home

    def _start_loop(self, home: Path, config: RaftConfig, sh: Shell) -> None:
        stack = Stack(root=home, apps=())
        docker = DockerStack(stack, sh)
        scaler = Scaler(home, docker)
        WakeHttpServer.bind(scaler, port=WAKE_HTTP_PORT)
        ControllerLoop(home, config, docker, scaler).run()
