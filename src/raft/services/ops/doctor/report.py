"""Group-first doctor report writer."""

from __future__ import annotations

import re
import sys
from typing import Optional, TextIO

from ....models import Stack, display_service_label
from ....ui import BOLD, CYAN, DIM, GREEN, RED, YELLOW, paint, want_color
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
        by_member, group_order, ungrouped = self._layout(stack, results)

        def tint(text: str, *codes: str) -> str:
            return paint(text, *codes, color=use_color)

        self._emit_groups(group_order, by_member, stream=stream, tint=tint)
        self._emit_ungrouped(ungrouped, by_member, stream=stream, tint=tint)
        return self._emit_summary(results, stream=stream, tint=tint)

    def _emit_groups(self, group_order, by_member, *, stream, tint) -> None:
        first_block = True
        for group_name, members in group_order:
            if not first_block:
                print(file=stream)
            first_block = False
            assert group_name is not None
            print(tint(group_name, BOLD, YELLOW), file=stream)
            for member in members:
                self._emit_member(
                    member, by_member=by_member, stream=stream, tint=tint,
                    indent="  ", group=group_name,
                )

    def _emit_ungrouped(self, ungrouped, by_member, *, stream, tint) -> None:
        if not ungrouped:
            return
        print(file=stream)
        for member in ungrouped:
            self._emit_member(
                member, by_member=by_member, stream=stream, tint=tint,
                indent="", group=None,
            )

    def _layout(
        self, stack: Stack, results: list[CheckResult]
    ) -> tuple[dict[str, list[CheckResult]], list[tuple[Optional[str], list[str]]], list[str]]:
        by_service: dict[str, list[CheckResult]] = {}
        for r in results:
            by_service.setdefault(r.service, []).append(r)
        infra_keys = {r.check for r in by_service.get(INFRA, [])}
        by_member = self._members_from_service(by_service)
        grouped, ungrouped = self._app_groups(stack)
        raft_members = self._assemble_raft_members(
            stack, by_member, infra_keys, grouped
        )
        group_order: list[tuple[Optional[str], list[str]]] = [
            (RAFT_GROUP, raft_members)
        ]
        for group in sorted(grouped):
            group_order.append((group, list(grouped[group])))
        ungrouped = self._append_orphans(by_member, group_order, ungrouped)
        return by_member, group_order, ungrouped

    @staticmethod
    def _members_from_service(
        by_service: dict[str, list[CheckResult]],
    ) -> dict[str, list[CheckResult]]:
        by_member: dict[str, list[CheckResult]] = {
            name: list(items)
            for name, items in by_service.items()
            if name != INFRA
        }
        for r in by_service.get(INFRA, []):
            by_member.setdefault(r.check, []).append(r)
        return by_member

    @staticmethod
    def _app_groups(stack: Stack) -> tuple[dict[str, list[str]], list[str]]:
        grouped: dict[str, list[str]] = {}
        ungrouped: list[str] = []
        for app in stack.apps:
            if app.group:
                grouped.setdefault(app.group, []).append(app.compose_id)
            else:
                ungrouped.append(app.compose_id)
        return grouped, ungrouped

    def _assemble_raft_members(
        self,
        stack: Stack,
        by_member: dict[str, list[CheckResult]],
        infra_keys: set[str],
        grouped: dict[str, list[str]],
    ) -> list[str]:
        raft_members = self._raft_member_order(by_member, infra_keys)
        insert_at = len(raft_members)
        for marker in ("generated", "compose.yaml", "docker"):
            if marker in raft_members:
                insert_at = raft_members.index(marker) + 1
                break
        for edge in (stack.gate, stack.router, stack.controller):
            if edge not in raft_members:
                raft_members.insert(insert_at, edge)
                insert_at += 1
            by_member.setdefault(edge, [])
        for name in grouped.pop(RAFT_GROUP, []):
            if name not in raft_members:
                raft_members.append(name)
        return [
            m
            for m in raft_members
            if not self._hide_healthy_infra(m, by_member.get(m, []))
        ]

    def _append_orphans(
        self,
        by_member: dict[str, list[CheckResult]],
        group_order: list[tuple[Optional[str], list[str]]],
        ungrouped: list[str],
    ) -> list[str]:
        listed = {m for _, members in group_order for m in members}
        listed.update(ungrouped)
        orphans = [
            n
            for n in sorted(by_member)
            if n not in listed
            and not self._hide_healthy_infra(n, by_member.get(n, []))
        ]
        return ungrouped + orphans

    def _emit_member(
        self,
        member: str,
        *,
        by_member: dict[str, list[CheckResult]],
        stream: TextIO,
        tint,
        indent: str,
        group: Optional[str],
    ) -> None:
        items = by_member.get(member, [])
        bad = [r for r in items if r.status != "ok"]
        label = display_service_label(member, group)
        print(tint(f"{indent}{label}", BOLD, CYAN), file=stream)
        body = indent + "  "
        if not bad:
            self._emit_ok_line(items, body=body, stream=stream, tint=tint)
            return
        for r in bad:
            self._emit_bad_result(r, body=body, stream=stream, tint=tint)

    def _emit_ok_line(self, items: list[CheckResult], *, body: str, stream, tint) -> None:
        label = tint(_STATUS_LABEL["ok"], _STATUS_COLOR["ok"], BOLD)
        ports = self._ok_ports_note(items)
        if ports:
            print(f"{body}{label}  {ports}", file=stream)
        else:
            print(f"{body}{label}", file=stream)

    @staticmethod
    def _emit_bad_result(r: CheckResult, *, body: str, stream, tint) -> None:
        status = tint(_STATUS_LABEL[r.status], _STATUS_COLOR[r.status], BOLD)
        print(f"{body}{status}", file=stream)
        print(f"{body}  {r.detail}", file=stream)
        if not r.fix:
            return
        fix_lines = r.fix.splitlines() or [""]
        print(f"{body}  {tint('fix → ' + fix_lines[0], DIM, CYAN)}", file=stream)
        for line in fix_lines[1:]:
            print(f"{body}         {tint(line, DIM, CYAN)}", file=stream)

    @staticmethod
    def _emit_summary(results: list[CheckResult], *, stream, tint) -> int:
        fails = sum(1 for r in results if r.status == "fail")
        warns = sum(1 for r in results if r.status == "warn")
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
