"""Shared metrics JSONL sample builders for read.metrics unit tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from raft.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME


def write_jsonl(home: Path, rows: List[Dict[str, Any]]) -> Path:
    path = home / METRICS_DIR / METRICS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8",
    )
    return path


def host_block(*, mem_pct: float, load1: float, cpus: int) -> Dict[str, Any]:
    return {
        "cpus": cpus,
        "loadavg": [load1, 0.2, 0.1],
        "memory": {
            "used_percent": mem_pct,
            "used_bytes": 1000,
            "total_bytes": 2000,
            "available_bytes": 1000,
        },
    }


def container_block(*, service: str, cpu: float, mem_pct: float) -> Dict[str, Any]:
    return {
        "service": service,
        "role": "gate",
        "group": "raft",
        "cpu_percent": cpu,
        "uptime_seconds": 120.0,
        "pids": 4,
        "memory": {
            "used_percent": mem_pct,
            "used_bytes": 500,
            "limit_bytes": 1000,
        },
        "network": {"rx_bytes": 11, "tx_bytes": 22},
        "block_io": {"read_bytes": 33, "write_bytes": 44},
    }


def sample(
    ts: datetime,
    *,
    cpu: float = 10.0,
    mem_pct: float = 40.0,
    service: str = "raft-gate",
    load1: float = 0.5,
    cpus: int = 2,
) -> Dict[str, Any]:
    return {
        "ts": ts.isoformat(),
        "host": host_block(mem_pct=mem_pct, load1=load1, cpus=cpus),
        "containers": [container_block(service=service, cpu=cpu, mem_pct=mem_pct)],
    }


def multi_sample(
    ts: datetime, services: List[str], *, cpu: float = 1.0
) -> Dict[str, Any]:
    return {
        "ts": ts.isoformat(),
        "host": host_block(mem_pct=40.0, load1=0.5, cpus=2),
        "containers": [
            container_block(service=name, cpu=cpu + i, mem_pct=10.0 + i)
            for i, name in enumerate(services)
        ],
    }
