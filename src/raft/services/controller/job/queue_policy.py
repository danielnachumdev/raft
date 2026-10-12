"""Queue policy when a job is already running."""

from enum import Enum


class QueuePolicy(Enum):
    SKIP_IF_RUNNING = "skipIfRunning"
    QUEUE = "queue"
    REPLACE = "replace"
