"""Compile ordered firewall rules into efficient gate nginx fragments."""

import ipaddress
from dataclasses import dataclass
from typing import Optional

from raft.core.core.models.firewall import FirewallRule, SERVICE_ANY
from raft.core.lifecycle.render.acl.nginx_text import FORBIDDEN_ALIAS


@dataclass(frozen=True)
class CompiledAccess:
    """One allow/deny directive after compile-time optimization."""

    verb: str
    cidr: str


@dataclass(frozen=True)
class CompiledFragment:
    """Location-body rules + optional drop CIDRs for an http-level geo map."""

    access: tuple[CompiledAccess, ...]
    drop_cidrs: tuple[str, ...]
    scope: str

    def is_active(self) -> bool:
        return bool(self.access) or bool(self.drop_cidrs)


class FirewallCompiler:
    """Heavy work at Save/render: first-match, merge, emit nginx text."""

    def compile_for(
        self,
        rules: tuple[FirewallRule, ...],
        *,
        port: int,
        service: str,
        scope: str,
    ) -> CompiledFragment:
        applicable = [
            rule
            for rule in rules
            if rule.matches_http_edge()
            and rule.applies_to_port(port)
            and rule.applies_to_service(service)
        ]
        optimized = self._optimize(applicable)
        return self._emit(optimized, scope=scope)

    def location_text(
        self, fragment: CompiledFragment, *, indent: str = "        "
    ) -> str:
        if not fragment.is_active():
            return ""
        lines = [
            f"{indent}# raft firewall scope={fragment.scope} (ordered; first match)",
        ]
        if fragment.drop_cidrs:
            var = self.drop_var(fragment.scope)
            lines.append(f"{indent}if (${var}) {{ return 444; }}")
        if fragment.access:
            lines.append(f"{indent}error_page 403 =403 /_raft_forbidden;")
            for item in fragment.access:
                lines.append(f"{indent}{item.verb} {item.cidr};")
        return "\n".join(lines) + "\n"

    def geo_map_text(self, fragment: CompiledFragment) -> str:
        if not fragment.drop_cidrs:
            return ""
        var = self.drop_var(fragment.scope)
        lines = [
            f"# raft firewall drop map scope={fragment.scope}",
            f"geo $remote_addr ${var} {{",
            "    default 0;",
        ]
        for cidr in fragment.drop_cidrs:
            lines.append(f"    {cidr} 1;")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def drop_var(scope: str) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in scope)
        return f"raft_fw_drop_{safe}"

    @staticmethod
    def forbidden_location(*, indent: str = "    ") -> str:
        return (
            f"{indent}location = /_raft_forbidden {{\n"
            f"{indent}    internal;\n"
            f"{indent}    default_type text/html;\n"
            f"{indent}    alias {FORBIDDEN_ALIAS};\n"
            f"{indent}}}\n"
        )

    def _emit(self, rules: list[FirewallRule], *, scope: str) -> CompiledFragment:
        access: list[CompiledAccess] = []
        drops: list[str] = []
        for rule in rules:
            if rule.action == "drop":
                drops.append(rule.cidr)
            elif rule.action == "permit":
                access.append(CompiledAccess("allow", rule.cidr))
            else:
                access.append(CompiledAccess("deny", rule.cidr))
        return CompiledFragment(
            access=tuple(access), drop_cidrs=tuple(drops), scope=scope
        )

    def _optimize(self, rules: list[FirewallRule]) -> list[FirewallRule]:
        if not rules:
            return []
        merged: list[FirewallRule] = [rules[0]]
        for rule in rules[1:]:
            self._merge_or_append(merged, rule)
        return merged

    def _merge_or_append(
        self, merged: list[FirewallRule], rule: FirewallRule
    ) -> None:
        prev = merged[-1]
        if not self._same_bucket(prev, rule):
            merged.append(rule)
            return
        collapsed = self._collapse_cidrs(prev.cidr, rule.cidr)
        if collapsed is None:
            merged.append(rule)
            return
        merged[-1] = FirewallRule(
            id=prev.id,
            cidr=collapsed,
            port=prev.port,
            protocol=prev.protocol,
            service=prev.service,
            action=prev.action,
        )

    @staticmethod
    def _same_bucket(left: FirewallRule, right: FirewallRule) -> bool:
        return (
            left.action == right.action
            and left.port == right.port
            and left.protocol == right.protocol
            and left.service.lower() == right.service.lower()
        )

    @staticmethod
    def _collapse_cidrs(left: str, right: str) -> Optional[str]:
        try:
            nets = [
                ipaddress.ip_network(left, strict=False),
                ipaddress.ip_network(right, strict=False),
            ]
        except ValueError:
            return None
        if nets[0].version != nets[1].version:
            return None
        collapsed = list(ipaddress.collapse_addresses(nets))
        if len(collapsed) != 1:
            return None
        return str(collapsed[0])


def scope_name(*, service: str, port: int) -> str:
    label = SERVICE_ANY if service.strip().lower() in {"", SERVICE_ANY} else service
    safe = "".join(ch if ch.isalnum() else "_" for ch in label)
    return f"{safe}_p{port}"
