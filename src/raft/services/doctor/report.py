"""Group-first doctor report writer."""

from __future__ import annotations

import re
import sys
from typing import Optional, TextIO

from ...models import Stack, display_service_label
from ...ui import BOLD, CYAN, DIM, GREEN, RED, YELLOW, paint, want_color
from .models import (
    INFRA,
    RAFT_GROUP,
    RAFT_MEMBER_ORDER,
    CheckResult,
)

_STATUS_LABEL = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
_STATUS_COLOR = {"ok": GREEN, "warn": YELLOW, "fail": RED}

# Host/platform members under ``raft`` — hide when fully healthy.
_INFRA_NOISE = frozenset(RAFT_MEMBER_ORDER)
_PORT_MEMBER_RE = re.compile(r"^port \d+")


class GroupReportWriter:
    """Render CheckResults as group → service + status (or flat ungrouped)."""

    def write(
        self,
        stack: Stack,
        results: list[CheckResult],
        *,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
    ) -> int:
        stream = out if out is not None else sys.stdout
        use_color = want_color(stream, color)

        by_service: dict[str, list[CheckResult]] = {}
        for r in results:
            by_service.setdefault(r.service, []).append(r)

        infra_keys = {r.check for r in by_service.get(INFRA, [])}
        by_member: dict[str, list[CheckResult]] = {
            name: list(items)
            for name, items in by_service.items()
            if name != INFRA
        }
        for r in by_service.get(INFRA, []):
            by_member.setdefault(r.check, []).append(r)

        grouped: dict[str, list[str]] = {}
        ungrouped: list[str] = []
        for app in stack.apps:
            cid = app.compose_id
            if app.group:
                grouped.setdefault(app.group, []).append(cid)
            else:
                ungrouped.append(cid)

        raft_members = self._raft_member_order(by_member, infra_keys)
        insert_at = len(raft_members)
        for marker in ("generated", "compose.yaml", "docker"):
            if marker in raft_members:
                insert_at = raft_members.index(marker) + 1
                break
        for edge in (stack.gate, stack.router):
            if edge not in raft_members:
                raft_members.insert(insert_at, edge)
                insert_at += 1
            by_member.setdefault(edge, [])

        # Apps that opted into the built-in raft group sit with edge + host probes.
        for name in grouped.pop(RAFT_GROUP, []):
            if name not in raft_members:
                raft_members.append(name)

        raft_members = [
            m
            for m in raft_members
            if not self._hide_healthy_infra(m, by_member.get(m, []))
        ]

        group_order: list[tuple[Optional[str], list[str]]] = [
            (RAFT_GROUP, raft_members)
        ]
        for group in sorted(grouped):
            group_order.append((group, list(grouped[group])))

        listed = {m for _, members in group_order for m in members}
        listed.update(ungrouped)
        orphans = [n for n in sorted(by_member) if n not in listed]
        orphans = [
            n
            for n in orphans
            if not self._hide_healthy_infra(n, by_member.get(n, []))
        ]
        ungrouped.extend(orphans)

        def tint(text: str, *codes: str) -> str:
            return paint(text, *codes, color=use_color)

        fails = sum(1 for r in results if r.status == "fail")
        warns = sum(1 for r in results if r.status == "warn")
        first_block = True

        def emit_member(
            member: str, *, indent: str, group: Optional[str] = None
        ) -> None:
            items = by_member.get(member, [])
            bad = [r for r in items if r.status != "ok"]
            label = display_service_label(member, group)
            print(tint(f"{indent}{label}", BOLD, CYAN), file=stream)
            body = indent + "  "
            if not bad:
                label = tint(_STATUS_LABEL["ok"], _STATUS_COLOR["ok"], BOLD)
                ports = self._ok_ports_note(items)
                if ports:
                    print(f"{body}{label}  {ports}", file=stream)
                else:
                    print(f"{body}{label}", file=stream)
                return
            for r in bad:
                status = tint(
                    _STATUS_LABEL[r.status],
                    _STATUS_COLOR[r.status],
                    BOLD,
                )
                print(f"{body}{status}", file=stream)
                print(f"{body}  {r.detail}", file=stream)
                if r.fix:
                    fix_lines = r.fix.splitlines() or [""]
                    print(
                        f"{body}  {tint('fix → ' + fix_lines[0], DIM, CYAN)}",
                        file=stream,
                    )
                    for line in fix_lines[1:]:
                        print(
                            f"{body}         {tint(line, DIM, CYAN)}",
                            file=stream,
                        )

        for group_name, members in group_order:
            if not first_block:
                print(file=stream)
            first_block = False
            assert group_name is not None
            print(tint(group_name, BOLD, YELLOW), file=stream)
            for member in members:
                emit_member(member, indent="  ", group=group_name)

        if ungrouped:
            print(file=stream)
            for member in ungrouped:
                emit_member(member, indent="")

        print(file=stream)
        if fails:
            print(tint(f"{fails} check(s) failed", RED, BOLD), file=stream)
            return 1
        if warns:
            print(tint(f"ok ({warns} warning(s))", YELLOW), file=stream)
        else:
            print(tint("all checks passed", GREEN, BOLD), file=stream)
        return 0

    @staticmethod
    def _hide_healthy_infra(member: str, items: list[CheckResult]) -> bool:
        """Drop docker/compose/generated/stack/port probes when they are all OK."""
        if not items:
            return False
        if any(r.status != "ok" for r in items):
            return False
        if member in _INFRA_NOISE:
            return True
        if _PORT_MEMBER_RE.match(member):
            return True
        return False

    @staticmethod
    def _ok_ports_note(items: list[CheckResult]) -> str:
        """Ports to show after OK — from a healthy ``ports`` check detail."""
        for r in items:
            if r.check == "ports" and r.status == "ok" and r.detail.strip():
                return r.detail.strip()
        return ""

    @staticmethod
    def _raft_member_order(
        by_member: dict[str, list[CheckResult]],
        infra_keys: set[str],
    ) -> list[str]:
        ordered: list[str] = []
        for key in RAFT_MEMBER_ORDER:
            if key in by_member and key not in ordered:
                ordered.append(key)
        rest = sorted(n for n in infra_keys if n in by_member and n not in ordered)
        ordered.extend(rest)
        return ordered
