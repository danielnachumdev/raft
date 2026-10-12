"""Shared serve app-factory fixtures (status snapshots + TestClient helpers)."""

import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from raft.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME
from raft.models.app import EDGE_GROUP
from raft.models.stack import Stack
from raft.ops.logs import Logs
from raft.ops.status import Status
from raft.ops.status.models import StatusSnapshot
from raft.serve.actions import ServeActions
from raft.serve.app import ServeAppFactory

from tests.unit.base import write_applied_app
from tests.unit.ops.status.fixtures import StatusFixtures


class ServeFixtures:
    @staticmethod
    def full_snapshot() -> StatusSnapshot:
        fx = StatusFixtures
        return StatusSnapshot(
            host=fx.empty_host_status(),
            containers=(
                fx.container("raft-gate", role="gate", group=EDGE_GROUP),
                fx.container("raft-router", role="router", group=EDGE_GROUP),
                fx.container("raft-controller", role="controller", group=EDGE_GROUP),
                fx.container(
                    "site", role="app", app="site", status="not running", uptime=None
                ),
            ),
        )

    @staticmethod
    def empty_snapshot() -> StatusSnapshot:
        return StatusSnapshot(host=StatusFixtures.empty_host_status(), containers=())

    @staticmethod
    def client_and_status(stack, snapshot: StatusSnapshot):
        status = MagicMock()
        status.collect.return_value = snapshot
        return TestClient(ServeAppFactory(stack, status=status).create()), status

    @staticmethod
    def client_with_actions(stack, actions):
        status = MagicMock()
        status.collect.return_value = ServeFixtures.empty_snapshot()
        return TestClient(
            ServeAppFactory(stack, status=status, actions=actions).create()
        )

    @staticmethod
    def write_metrics_sample(stack, *, ts: str) -> None:
        path = stack.root / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": ts,
            "host": {"cpus": 2, "loadavg": [1.0], "memory": {"used_percent": 10}},
            "containers": [
                {
                    "service": "raft-gate",
                    "role": "gate",
                    "group": "raft",
                    "cpu_percent": 4.0,
                    "memory": {"used_percent": 20},
                }
            ],
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    @staticmethod
    def live_registry_client(root):
        write_applied_app(root, "site")
        stack = Stack.load_apps(root)
        status = Status(stack)
        StatusFixtures.mock_docker_idle(status)
        actions = ServeActions(stack)
        logs = Logs(stack)
        client = TestClient(
            ServeAppFactory(
                stack, status=status, actions=actions, logs=logs
            ).create()
        )
        return client, actions, logs

    @staticmethod
    def write_out_of_band_apps(root) -> None:
        write_applied_app(root, "demo-api")
        write_applied_app(
            root,
            "demo-worker",
            source="docker",
            image="ghcr.io/example/worker",
            public_host="",
            build_context=None,
            extra={"ports": [], "readiness": {"type": "none"}},
        )
