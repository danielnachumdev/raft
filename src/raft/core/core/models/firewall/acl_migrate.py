"""Migrate #195 flat ACL policies into an ordered :class:`FirewallDocument`."""

from pathlib import Path

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.acl_policy import AclEntry, AclPolicy
from raft.core.core.models.state.acl_store import AppAclStore
from .document import FirewallDocument
from .rule import FirewallRule, SERVICE_ANY


class AclV1Migrator:
    """Build ordered firewall rules from ``acl.gate`` + ``state/acl/apps``."""

    def __init__(self, root: Path, *, ports: tuple[int, ...] = (80, 443)) -> None:
        self._root = root
        self._ports = ports if ports else (80,)
        self._store = AppAclStore(root)

    def migrate(self) -> FirewallDocument:
        rules: list[FirewallRule] = []
        gate = SettingsLoader().load(self._root).acl.gate.to_policy()
        rules.extend(self._from_policy(gate, service=SERVICE_ANY, prefix="gate"))
        for name in self._store.list_names():
            policy = self._store.load(name)
            if not policy.is_active():
                continue
            rules.extend(self._from_policy(policy, service=name, prefix=f"app-{name}"))
        return FirewallDocument(rules=tuple(rules), source="acl-v1-migrated")

    def _from_policy(
        self, policy: AclPolicy, *, service: str, prefix: str
    ) -> list[FirewallRule]:
        if not policy.is_active():
            return []
        if policy.mode == "whitelist":
            return self._whitelist(policy.entries, service=service, prefix=prefix)
        return self._blacklist(policy.entries, service=service, prefix=prefix)

    def _whitelist(
        self, entries: tuple[AclEntry, ...], *, service: str, prefix: str
    ) -> list[FirewallRule]:
        rules: list[FirewallRule] = []
        for port in self._ports:
            rules.extend(
                self._permits_for_port(entries, service=service, prefix=prefix, port=port)
            )
            rules.append(
                self._rule(
                    f"{prefix}-default-p{port}-deny",
                    "0.0.0.0/0",
                    port,
                    service,
                    "deny",
                )
            )
        return rules

    def _permits_for_port(
        self,
        entries: tuple[AclEntry, ...],
        *,
        service: str,
        prefix: str,
        port: int,
    ) -> list[FirewallRule]:
        return [
            self._rule(
                f"{prefix}-{entry.id}-p{port}-permit",
                entry.cidr,
                port,
                service,
                "permit",
            )
            for entry in entries
        ]

    def _blacklist(
        self, entries: tuple[AclEntry, ...], *, service: str, prefix: str
    ) -> list[FirewallRule]:
        rules: list[FirewallRule] = []
        for port in self._ports:
            for entry in entries:
                rules.append(
                    self._rule(
                        f"{prefix}-{entry.id}-p{port}-deny",
                        entry.cidr,
                        port,
                        service,
                        "deny",
                    )
                )
        return rules

    @staticmethod
    def _rule(
        rule_id: str, cidr: str, port: int, service: str, action: str
    ) -> FirewallRule:
        return FirewallRule(
            id=rule_id,
            cidr=cidr,
            port=port,
            protocol="tcp",
            service=service,
            action=action,
        )
