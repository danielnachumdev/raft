"""``raft-controller`` process entry (prereq smoke, then heal + scale loop)."""

from __future__ import annotations

import logging
import time
from typing import Callable

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.errors import OperatorError
from raft.models.stack import Stack

from .heal import Healer
from .logging import setup_controller_logging
from .scale import WAKE_HTTP_PORT, Scaler
from .smoke import run_prereq_smoke
from .wake_http import start_wake_http

__all__ = ["main"]

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], None]


def main() -> None:
    # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
    # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
    home = raft_home()
    if not home.is_dir():
        raise OperatorError(
            f"raft data home missing: {home}\n"
            f"Fix: run `raft render` (or any raft command) on the host first"
        )
    config = load_config(home)
    setup_controller_logging(config)
    logger.info("raft-controller starting data_home=%s", home)
    sh = Shell(home)
    run_prereq_smoke(home, sh)
    logger.info("prereq smoke ok; entering control loop")
    stack = Stack(root=home, apps=())
    docker = DockerStack(stack, sh)
    scaler = Scaler(home, docker)
    start_wake_http(scaler, port=WAKE_HTTP_PORT)
    _run_forever(home, config.healing, docker, scaler)


def _run_forever(
    home,
    healing,
    docker: DockerStack,
    scaler: Scaler,
    *,
    sleep_fn: SleepFn = time.sleep,
) -> None:
    healer = Healer(home=home, config=healing, docker=docker)
    _log_startup(healing)
    while True:
        _safe_tick(healer.tick, "heal")
        _safe_tick(scaler.tick, "scale")
        sleep_fn(healing.interval_seconds)


def _safe_tick(fn: Callable[[], None], label: str) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 — keep the controller alive
        logger.exception("%s tick failed", label)


def _log_startup(healing) -> None:
    if healing.enabled:
        logger.info(
            "healing enabled interval=%ss failThreshold=%s",
            healing.interval_seconds,
            healing.fail_threshold,
        )
    else:
        logger.info("healing disabled; scale + idle wake loop active")
    logger.info("scale-to-zero enabled for apps with spec.scaling")
