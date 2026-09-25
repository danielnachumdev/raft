"""Exclusive flock helpers for overlapping raft apply / redeploy / render.

nginx and Docker Compose do not serialize raft's multi-step cutover. Concurrent
``raft apply`` / ``raft redeploy`` for the same app (or different apps that share
generated compose/nginx) can interleave upstream writes, compose recreate, and
tmp containers so a slower older deploy finishes last and wins live traffic.

Locks live under ``~/.raft/state/locks/`` (``RAFT_DATA_HOME``):

* ``app-<name>.lock`` — one mutative deploy/apply for that app at a time
* ``stack.lock`` — render, nginx reload, cutover, compose up/recreate, gate

Wait (with timeout) so a later-started deploy still runs after an earlier one
and becomes the final live state. Override budget via ``RAFT_LOCK_TIMEOUT_SECONDS``.
"""

from __future__ import annotations

import fcntl
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional

from raft.errors import deploy_lock_busy, invalid_lock_timeout

logger = logging.getLogger(__name__)

LOCKS_REL = Path("state") / "locks"
STACK_LOCK_NAME = "stack.lock"
ENV_LOCK_TIMEOUT = "RAFT_LOCK_TIMEOUT_SECONDS"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300.0
_POLL_INTERVAL_SECONDS = 0.05

# Per-thread nesting so redeploy → sync → render re-enters safely, while another
# thread still blocks on the real flock (process-global _held would wrongly nest).
_local = threading.local()


class _Held:
    __slots__ = ("path", "fd")

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd = fd


def _held_map() -> Dict[str, "_Held"]:
    held = getattr(_local, "held", None)
    if held is None:
        held = {}
        _local.held = held
    return held


def locks_dir(root: Path) -> Path:
    return root / LOCKS_REL


def stack_lock_path(root: Path) -> Path:
    return locks_dir(root) / STACK_LOCK_NAME


def app_lock_path(root: Path, name: str) -> Path:
    safe = name.replace("/", "_").replace("\\", "_")
    return locks_dir(root) / f"app-{safe}.lock"


def resolve_lock_timeout(override: Optional[float] = None) -> float:
    """Seconds to wait for a busy lock before ``OperatorError``."""
    if override is not None:
        if override < 0:
            raise invalid_lock_timeout(repr(override))
        return float(override)
    raw = os.environ.get(ENV_LOCK_TIMEOUT)
    if raw is None or not str(raw).strip():
        return DEFAULT_LOCK_TIMEOUT_SECONDS
    try:
        value = float(str(raw).strip())
    except ValueError as exc:
        raise invalid_lock_timeout(raw) from exc
    if value < 0:
        raise invalid_lock_timeout(raw)
    return value


def _key(path: Path) -> str:
    return str(path.resolve())


@contextmanager
def exclusive_lock(
    path: Path,
    *,
    kind: str,
    timeout: Optional[float] = None,
) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``path`` (create parent dirs as needed).

    Re-entrant for the same thread and resolved path. Waits up to ``timeout``
    seconds for another holder; then raises ``OperatorError``.
    """
    budget = resolve_lock_timeout(timeout)
    path = path.resolve()
    key = _key(path)
    held_map = _held_map()
    if key in held_map:
        yield
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + budget
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise deploy_lock_busy(kind, path)
                time.sleep(_POLL_INTERVAL_SECONDS)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise

    held = _Held(path, fd)
    held_map[key] = held
    logger.debug("acquired %s lock %s", kind, path)
    try:
        yield
    finally:
        _release(key, held)


def _release(key: str, held: _Held) -> None:
    try:
        fcntl.flock(held.fd, fcntl.LOCK_UN)
    finally:
        try:
            os.close(held.fd)
        except OSError:
            pass
        _held_map().pop(key, None)
        logger.debug("released lock %s", held.path)


@contextmanager
def app_deploy_lock(
    root: Path,
    name: str,
    *,
    timeout: Optional[float] = None,
) -> Iterator[None]:
    """Serialize mutative work for one app (apply deploy / redeploy / cutover)."""
    with exclusive_lock(
        app_lock_path(root, name),
        kind=f"app {name!r}",
        timeout=timeout,
    ):
        yield


@contextmanager
def stack_lock(root: Path, *, timeout: Optional[float] = None) -> Iterator[None]:
    """Serialize render / nginx reload / compose / cutover across all apps."""
    with exclusive_lock(
        stack_lock_path(root),
        kind="stack",
        timeout=timeout,
    ):
        yield


@contextmanager
def app_and_stack_locks(
    root: Path,
    name: str,
    *,
    timeout: Optional[float] = None,
) -> Iterator[None]:
    """Acquire app lock then stack lock (fixed order avoids cross-app deadlock)."""
    with app_deploy_lock(root, name, timeout=timeout):
        with stack_lock(root, timeout=timeout):
            yield
