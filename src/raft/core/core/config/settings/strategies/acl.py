"""Parse ``acl:`` from settings.yaml (gate-wide IP/CIDR access control)."""

from typing import Any

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from ..section import SettingsSectionParser
from ..types import AclConfig, GateAclConfig


class AclSettingsParser(SettingsSectionParser[AclConfig]):
    """Structural parse for durable gate ACL under ``acl:``."""

    def parse(self, raw: Any) -> AclConfig:
        if raw is None:
            return AclConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml acl must be a mapping.\n"
                "Fix: set acl: {gate: {mode: whitelist, entries: […]}} "
                "in ~/.raft/settings.yaml",
                has_fix=False,
            )
        return AclConfig(gate=self._gate(raw.get("gate")))

    def _gate(self, raw: Any) -> GateAclConfig:
        policy = AclPolicy.from_mapping(raw, path="acl.gate")
        return GateAclConfig(mode=policy.mode, entries=policy.entries)
