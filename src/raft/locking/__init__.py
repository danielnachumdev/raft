"""Cross-cutting flock helpers for mutative raft operations.

Locks live under ``~/.raft/state/locks/`` (``RAFT_DATA_HOME``):

* ``app-<name>.lock`` — one mutative deploy/apply for that app at a time
* ``stack.lock`` — render, nginx reload, cutover, compose up/recreate, gate,
  ``raft purge`` (Docker image/build-cache prune)
* ``notifications.lock`` — serve API rewrites of ``settings.yaml`` ``notifications:``

Wait (with timeout) so a later-started deploy still runs after an earlier one
and becomes the final live state. Contended waiters log ``waiting for … lock``
once, then ``acquired … lock`` when held. Override budget via
``RAFT_LOCK_TIMEOUT_SECONDS``.
"""

from .app_and_stack_locks import AppAndStackLocks
from .app_deploy_lock import AppDeployLock
from .apps_and_stack_locks import AppsAndStackLocks
from .exclusive import ExclusiveLock
from .notifications_lock import NotificationsLock
from .paths import LockPaths
from .stack_lock import StackLock
from .timeout import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    ENV_LOCK_TIMEOUT,
    LockTimeout,
)

__all__ = [
    "AppAndStackLocks",
    "AppDeployLock",
    "AppsAndStackLocks",
    "DEFAULT_LOCK_TIMEOUT_SECONDS",
    "ENV_LOCK_TIMEOUT",
    "ExclusiveLock",
    "LockPaths",
    "LockTimeout",
    "NotificationsLock",
    "StackLock",
]
