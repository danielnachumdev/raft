"""Run ``raft serve`` with a fake Docker status collector (no Engine needed).

Usage: RAFT_DATA_HOME=/tmp/raft-demo/home uv run python scripts/serve_demo/serve.py --port 8821

Patches ``Status.collect`` so every applied App gets a canned runtime row
(running / unhealthy / scaled-to-zero) and the host reports ``demo-host``.
Pair with ``seed_home.py``; never point ``RAFT_DATA_HOME`` at a real home.
"""

import os
import sys

if not os.environ.get("RAFT_DATA_HOME"):
    sys.exit("set RAFT_DATA_HOME to a seeded demo home (see seed_home.py)")

from raft.core.observe.ops.status import service as status_service
from raft.core.observe.ops.status.models import (
    AllocatedResources,
    ContainerStatus,
    HostStatus,
    IoPair,
    MemoryUsage,
    StatusSnapshot,
)

FAKE = {
    "raft-gate": ("running", 1.2, 18, 32),
    "raft-router": ("running", 0.6, 9, 32),
    "raft-controller": ("running", 2.4, 54, 192),
    "demo-api": ("running", 27.5, 210, 512),
    "demo-web": ("running", 9.1, 140, 512),
    "demo-db": ("unhealthy", 5.3, 300, 1024),
    "demo-worker": ("running", 52.0, 260, 512),
    "demo-docs": ("scaled-to-zero", None, None, 256),
}


def _container(svc, role, app, group, allocated):
    key = next((k for k in FAKE if svc == k or svc.endswith("-" + k) or svc.startswith(k)), None)
    status, cpu, used, limit = FAKE.get(key, ("not running", None, None, 256))
    up = status == "running" or status == "unhealthy"
    mib = 1024 * 1024
    return ContainerStatus(
        service=svc, role=role, app=app, group=group, status=status,
        uptime_seconds=93_000.0 if up else None, cpu_percent=cpu,
        memory=MemoryUsage(used * mib if used else None, limit * mib, (used / limit * 100) if used else None),
        allocated=allocated,
        network=IoPair(48_000_000 if up else None, 91_000_000 if up else None),
        block_io=IoPair(3_000_000 if up else None, 12_000_000 if up else None),
        pids=14 if up else None,
    )


def collect(self, *, refresh_apps=False):
    if refresh_apps:
        self._reload_stack()
    containers = tuple(_container(*t) for t in self._targets())
    gib = 1024 ** 3
    host = HostStatus(
        hostname="demo-host",
        fqdn="demo-host.example.test",
        cpus=4,
        loadavg=(0.82, 0.71, 0.66),
        memory=MemoryUsage(5 * gib, 8 * gib, 62.5),
        memory_total_bytes=8 * gib,
        memory_available_bytes=3 * gib,
        disk_path="/",
        disk_total_bytes=80 * gib,
        disk_used_bytes=34 * gib,
        disk_free_bytes=46 * gib,
        disk_used_percent=42.5,
        uptime_seconds=1_200_000.0,
    )
    return StatusSnapshot(host=host, containers=containers)


status_service.Status.collect = collect

from raft.services.serve.entry import main  # noqa: E402

sys.argv = ["serve"] + sys.argv[1:]
main()
