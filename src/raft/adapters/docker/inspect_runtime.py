"""Parse Docker Engine inspect / stats JSON into runtime fact dicts."""

import json
import logging
from typing import Any, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


class InspectRuntime:
    """Pure parsers for ``docker inspect`` / ``docker stats`` payloads."""

    @classmethod
    def from_inspect_json(cls, stdout: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(stdout.strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return cls.from_inspect_dict(data)

    @classmethod
    def from_inspect_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        state = data.get("State") if isinstance(data.get("State"), dict) else {}
        host = data.get("HostConfig") if isinstance(data.get("HostConfig"), dict) else {}
        health_obj = state.get("Health")
        health = "none"
        if isinstance(health_obj, dict):
            health = str(health_obj.get("Status") or "none")
        return {
            "status": str(state.get("Status") or "unknown"),
            "health": health or "none",
            "started_at": str(state.get("StartedAt") or ""),
            "finished_at": str(state.get("FinishedAt") or ""),
            "restart_count": cls._restart_count(data.get("RestartCount")),
            "oom_killed": bool(state.get("OOMKilled")),
            "exit_code": cls._optional_int(state.get("ExitCode")),
            "nano_cpus": cls._optional_int(host.get("NanoCpus")),
            "memory_bytes": cls._optional_int(host.get("Memory")),
        }

    @classmethod
    def index_stats_rows(
        cls, stdout: str, container_ids: Sequence[str]
    ) -> Dict[str, Dict[str, Any]]:
        by_id: Dict[str, Dict[str, Any]] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            row = cls._parse_stats_line(line)
            if row is None:
                continue
            raw_id = str(row.get("ID") or row.get("Container") or "").strip()
            if not raw_id:
                continue
            by_id[raw_id] = row
            for cid in container_ids:
                if cid.startswith(raw_id) or raw_id.startswith(cid):
                    by_id[cid] = row
        return by_id

    @staticmethod
    def _parse_stats_line(line: str) -> Optional[Dict[str, Any]]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("skip unparseable docker stats line: %r", line)
            return None
        return row if isinstance(row, dict) else None

    @classmethod
    def _restart_count(cls, raw: Any) -> int:
        value = cls._optional_int(raw)
        return value if value is not None and value >= 0 else 0

    @staticmethod
    def _optional_int(raw: Any) -> Optional[int]:
        if isinstance(raw, bool) or raw is None:
            return None
        if isinstance(raw, int):
            return raw
        text = str(raw).strip()
        return int(text) if text.isdigit() else None
