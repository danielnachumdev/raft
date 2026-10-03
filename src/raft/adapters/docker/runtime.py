"""Batch container runtime facts via Docker Engine (not ``compose ps``)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from ...models.app import COMPOSE_PROJECT
from ..shell import Shell
from .inspect import DockerInspect

logger = logging.getLogger(__name__)

_PS_FORMAT = '{{.ID}}\t{{.Label "com.docker.compose.service"}}'
_LABEL_PROJECT = "com.docker.compose.project"


@dataclass(frozen=True)
class ContainerRuntimeRow:
    """Runtime + stats for one Compose service container."""

    container_id: str
    status: str
    health: str
    started_at: str
    memory_bytes: Optional[int]
    stats: Optional[Dict[str, Any]]
    restart_count: int = 0
    oom_killed: bool = False
    finished_at: str = ""
    exit_code: Optional[int] = None


class ContainerRuntimeGateway:
    """Single source of truth for Compose-project container resource facts.

    Uses ``docker ps`` / ``inspect`` / ``stats`` (Engine API), not
    ``docker compose ps``. That avoids Compose-file include conflicts inside
    ``raft-controller`` (older Compose rejects merged ``raft-router``).
    """

    def __init__(self, sh: Shell, *, project: str = COMPOSE_PROJECT) -> None:
        self._sh = sh
        self._project = project

    def collect(self, services: Sequence[str]) -> Dict[str, ContainerRuntimeRow]:
        """One-shot facts for ``services`` that currently have a container."""
        if not services:
            return {}
        id_by_service = self._running_ids()
        wanted = {name: id_by_service[name] for name in services if name in id_by_service}
        if not wanted:
            return {}
        ids = list(dict.fromkeys(wanted.values()))
        runtime_by_id = self._inspect_many(ids)
        stats_by_id = self._stats_many(ids)
        return self._rows_for(wanted, runtime_by_id, stats_by_id)

    def _running_ids(self) -> Dict[str, str]:
        result = self._sh.docker(
            "ps",
            "--filter",
            f"label={_LABEL_PROJECT}={self._project}",
            "--format",
            _PS_FORMAT,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "docker ps project=%s failed rc=%s: %s",
                self._project,
                result.returncode,
                (result.stderr or "").strip(),
            )
            return {}
        return self._parse_ps(result.stdout or "")

    @staticmethod
    def _parse_ps(stdout: str) -> Dict[str, str]:
        by_service: Dict[str, str] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line or "\t" not in line:
                continue
            cid, service = line.split("\t", 1)
            # Line strip already dropped edge-only whitespace fields.
            by_service[service.strip()] = cid.strip()
        return by_service

    def _inspect_many(self, container_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not container_ids:
            return {}
        result = self._sh.docker(
            "inspect",
            *container_ids,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "docker inspect batch failed rc=%s: %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return {}
        return self._index_inspect(result.stdout or "", container_ids)

    @staticmethod
    def _index_inspect(
        stdout: str, container_ids: Sequence[str]
    ) -> Dict[str, Dict[str, Any]]:
        try:
            payload = json.loads(stdout.strip() or "[]")
        except json.JSONDecodeError:
            return {}
        items = payload if isinstance(payload, list) else [payload]
        by_id: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            runtime = DockerInspect._runtime_from_inspect_dict(item)
            raw_id = str(item.get("Id") or "").strip()
            ContainerRuntimeGateway._store_runtime(by_id, raw_id, runtime, container_ids)
        return by_id

    @staticmethod
    def _store_runtime(
        by_id: Dict[str, Dict[str, Any]],
        raw_id: str,
        runtime: Dict[str, Any],
        container_ids: Sequence[str],
    ) -> None:
        if not raw_id:
            return
        by_id[raw_id] = runtime
        for cid in container_ids:
            if cid.startswith(raw_id) or raw_id.startswith(cid):
                by_id[cid] = runtime

    def _stats_many(self, container_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not container_ids:
            return {}
        result = self._sh.docker(
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *container_ids,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "docker stats failed rc=%s: %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return {}
        return DockerInspect._index_stats_rows(result.stdout or "", list(container_ids))

    @staticmethod
    def _rows_for(
        wanted: Mapping[str, str],
        runtime_by_id: Mapping[str, Dict[str, Any]],
        stats_by_id: Mapping[str, Dict[str, Any]],
    ) -> Dict[str, ContainerRuntimeRow]:
        rows: Dict[str, ContainerRuntimeRow] = {}
        for service, cid in wanted.items():
            rows[service] = ContainerRuntimeGateway._one_row(
                cid, runtime_by_id.get(cid) or {}, stats_by_id.get(cid)
            )
        return rows

    @staticmethod
    def _one_row(
        cid: str,
        runtime: Mapping[str, Any],
        stats: Optional[Dict[str, Any]],
    ) -> ContainerRuntimeRow:
        mem = runtime.get("memory_bytes")
        exit_code = runtime.get("exit_code")
        return ContainerRuntimeRow(
            container_id=cid,
            status=str(runtime.get("status") or "unknown"),
            health=str(runtime.get("health") or "none"),
            started_at=str(runtime.get("started_at") or ""),
            memory_bytes=mem if isinstance(mem, int) else None,
            stats=stats,
            restart_count=int(runtime.get("restart_count") or 0),
            oom_killed=bool(runtime.get("oom_killed")),
            finished_at=str(runtime.get("finished_at") or ""),
            exit_code=exit_code if isinstance(exit_code, int) else None,
        )
