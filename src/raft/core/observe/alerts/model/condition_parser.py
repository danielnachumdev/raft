"""Parse condition trees from YAML/JSON mappings."""

from typing import Any, List, Mapping

from raft.core.core.errors.cta import OperatorError

from ..constants import MAX_DEPTH, MAX_LEAVES
from .condition import ConditionGroup, ConditionLeaf, ConditionNode
from .issues import ValidationIssue, ValidationReport


class ConditionParser:
    """Parse a condition node with depth and leaf limits."""

    def parse(self, raw: Any, path: str = "condition") -> ConditionNode:
        report = ValidationReport()
        node = self._parse(raw, path, depth=0, report=report, leaf_count=[0])
        if report.errors:
            raise OperatorError(self._format(report))
        return node

    def validate(self, raw: Any, path: str = "condition") -> ValidationReport:
        report = ValidationReport()
        self._parse(raw, path, depth=0, report=report, leaf_count=[0])
        return report

    def _parse(
        self,
        raw: Any,
        path: str,
        *,
        depth: int,
        report: ValidationReport,
        leaf_count: List[int],
    ) -> ConditionNode:
        if depth > MAX_DEPTH:
            report.add_error(path, f"condition depth exceeds {MAX_DEPTH}")
            return ConditionLeaf("", {}, "", {})
        if not isinstance(raw, Mapping):
            report.add_error(path, "condition must be a mapping")
            return ConditionLeaf("", {}, "", {})
        if "all" in raw or "any" in raw:
            return self._group(raw, path, depth=depth, report=report, leaf_count=leaf_count)
        return self._leaf(raw, path, report=report, leaf_count=leaf_count)

    def _group(
        self,
        raw: Mapping[str, Any],
        path: str,
        *,
        depth: int,
        report: ValidationReport,
        leaf_count: List[int],
    ) -> ConditionGroup:
        op = self._group_op(raw, path, report)
        children_raw = raw.get(op) if op else None
        if not self._valid_children(children_raw, path, op, report):
            return ConditionGroup(op or "all", ())
        children = self._group_children(
            children_raw, path, op, depth=depth, report=report, leaf_count=leaf_count
        )
        return ConditionGroup(op, tuple(children))

    def _group_op(self, raw: Mapping[str, Any], path: str, report: ValidationReport) -> str:
        keys = [k for k in ("all", "any") if k in raw]
        if len(keys) != 1 or len(raw) != 1:
            report.add_error(path, "group must be exactly {all: [...]} or {any: [...]}")
            return ""
        return keys[0]

    def _valid_children(self, children_raw, path, op, report) -> bool:
        if not isinstance(children_raw, list) or not children_raw:
            report.add_error(f"{path}.{op}", "group must have 1–8 children")
            return False
        if len(children_raw) > 8:
            report.add_error(f"{path}.{op}", "group may have at most 8 children")
        return True

    def _group_children(
        self, children_raw, path, op, *, depth, report, leaf_count
    ) -> List[ConditionNode]:
        children: List[ConditionNode] = []
        for i, child in enumerate(children_raw[:8]):
            children.append(
                self._parse(
                    child,
                    f"{path}.{op}[{i}]",
                    depth=depth + 1,
                    report=report,
                    leaf_count=leaf_count,
                )
            )
        return children

    def _leaf(
        self,
        raw: Mapping[str, Any],
        path: str,
        *,
        report: ValidationReport,
        leaf_count: List[int],
    ) -> ConditionLeaf:
        leaf_count[0] += 1
        if leaf_count[0] > MAX_LEAVES:
            report.add_error(path, f"more than {MAX_LEAVES} leaves")
        signal, kind, select, params = self._leaf_fields(raw, path, report)
        return ConditionLeaf(signal, select, kind, params)

    def _leaf_fields(self, raw, path, report):
        signal = raw.get("signal")
        kind = raw.get("kind")
        select = raw.get("select") or {}
        params = raw.get("params") or {}
        if not isinstance(signal, str) or not signal:
            report.add_error(f"{path}.signal", "signal is required")
            signal = ""
        if not isinstance(kind, str) or not kind:
            report.add_error(f"{path}.kind", "kind is required")
            kind = ""
        if not isinstance(select, Mapping):
            report.add_error(f"{path}.select", "select must be a mapping")
            select = {}
        if not isinstance(params, Mapping):
            report.add_error(f"{path}.params", "params must be a mapping")
            params = {}
        return signal, kind, dict(select), dict(params)

    @staticmethod
    def _format(report: ValidationReport) -> str:
        lines = [f"{i.path}: {i.message}" for i in report.errors]
        joined = "\n".join(f"- {line}" for line in lines)
        return f"invalid alert condition.\n{joined}\nFix: repair the condition tree"
