"""Persist gate ACL into ``~/.raft/settings.yaml`` ``acl:``."""

import os
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from raft.core.core.config.paths import RaftHome
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from raft.core.platform.locking import AclLock


class GateAclSettingsWriter:
    """Merge gate ACL into operator settings under flock."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._path = RaftHome().settings_path(data_home)

    def get_public(self) -> Dict[str, Any]:
        return self._load_policy().to_public()

    def put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with AclLock(self._home):
            policy = AclPolicy.from_mapping(body, path="acl.gate")
            self._persist(policy)
            return policy.to_public()

    def clear(self) -> Dict[str, Any]:
        return self.put({"mode": "off", "entries": []})

    def _load_policy(self) -> AclPolicy:
        return SettingsLoader().load(self._home).acl.gate.to_policy()

    def _persist(self, policy: AclPolicy) -> None:
        data = self._load_root()
        data["acl"] = {
            "gate": {
                "mode": policy.mode,
                "entries": [entry.to_public() for entry in policy.entries],
            }
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
        self._path.write_text(text, encoding="utf-8")
        os.chmod(self._path, 0o600)

    def _load_root(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot read settings.yaml for ACL write: {exc}.\n"
                f"Fix: repair ~/.raft/settings.yaml then retry",
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml must be a YAML mapping to write acl:.\n"
                "Fix: repair ~/.raft/settings.yaml",
                has_fix=False,
            )
        return raw
