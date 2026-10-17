"""Compose leaf results with three-valued all/any and subject join."""

from typing import Dict, List, Optional, Tuple

from ..model.condition import ConditionGroup, ConditionLeaf, ConditionNode
from ..model.rule import AlertRule
from ..registries import AlertRegistries
from ..signals.context import SignalContext
from .leaf_result import LeafValue, SubjectOutcome


class ConditionEvaluator:
    """Walk a condition tree and join subjects."""

    def __init__(self, registries: AlertRegistries) -> None:
        self._regs = registries

    def evaluate(
        self, rule: AlertRule, ctx: SignalContext
    ) -> List[SubjectOutcome]:
        subjects, matched, leaves = self._eval(rule.condition, "condition", ctx)
        out: List[SubjectOutcome] = []
        for subject in subjects:
            final = self._apply_no_data(matched.get(subject), rule.no_data)
            out.append(
                SubjectOutcome(subject, final, tuple(leaves.get(subject, ())))
            )
        return out

    def _eval(
        self, node: ConditionNode, path: str, ctx: SignalContext
    ) -> Tuple[List[str], Dict[str, Optional[bool]], Dict[str, Tuple[LeafValue, ...]]]:
        if isinstance(node, ConditionLeaf):
            return self._leaf(node, path, ctx)
        return self._group(node, path, ctx)

    def _leaf(
        self, leaf: ConditionLeaf, path: str, ctx: SignalContext
    ) -> Tuple[List[str], Dict[str, Optional[bool]], Dict[str, Tuple[LeafValue, ...]]]:
        source = self._regs.signals.get(leaf.signal)
        kind = self._regs.kinds.get(leaf.kind)
        window = kind.window_seconds(leaf.params)
        series_list = source.query(leaf.select, window_seconds=window, ctx=ctx)
        describe = source.describe(leaf.select)
        if not series_list:
            return self._leaf_empty(leaf, path, describe)
        return self._leaf_series(leaf, path, ctx, describe, kind, series_list)

    def _leaf_series(
        self, leaf, path, ctx, describe, kind, series_list
    ) -> Tuple[List[str], Dict[str, Optional[bool]], Dict[str, Tuple[LeafValue, ...]]]:
        matched: Dict[str, Optional[bool]] = {}
        leaves: Dict[str, Tuple[LeafValue, ...]] = {}
        subjects: List[str] = []
        wildcard = leaf.select.get("target") == "*"
        for series in series_list:
            key, row = self._leaf_row(
                leaf, path, ctx, describe, kind, series, wildcard
            )
            subjects.append(key)
            matched[key] = row.matched
            leaves[key] = (row,)
        return self._dedupe_subjects(subjects), matched, leaves

    def _leaf_row(self, leaf, path, ctx, describe, kind, series, wildcard):
        result = kind.evaluate(series, leaf.params, now=ctx.now)
        key = series.subject if (wildcard or series.subject) else "-"
        return key, LeafValue(
            path=path,
            signal=leaf.signal,
            describe=describe,
            value=result.value,
            matched=result.matched,
            detail=result.detail,
            no_data=result.matched is None,
        )

    def _leaf_empty(self, leaf, path, describe):
        target = str(leaf.select.get("target") or "-")
        key = "-" if target == "*" else target
        leaf_val = LeafValue(path, leaf.signal, describe, None, None, "no data", True)
        return [key], {key: None}, {key: (leaf_val,)}

    @staticmethod
    def _dedupe_subjects(subjects: List[str]) -> List[str]:
        seen: List[str] = []
        for s in subjects:
            if s not in seen:
                seen.append(s)
        return seen

    def _group(
        self, group: ConditionGroup, path: str, ctx: SignalContext
    ) -> Tuple[List[str], Dict[str, Optional[bool]], Dict[str, Tuple[LeafValue, ...]]]:
        children = [
            self._eval(child, f"{path}.{group.op}[{i}]", ctx)
            for i, child in enumerate(group.children)
        ]
        universe = self._universe(children)
        matched: Dict[str, Optional[bool]] = {}
        leaves: Dict[str, Tuple[LeafValue, ...]] = {}
        for subject in universe:
            values = []
            leaf_vals: List[LeafValue] = []
            for i, child_node in enumerate(group.children):
                m, lv = self._child_value(children[i], subject, child_node)
                values.append(m)
                leaf_vals.extend(lv)
            matched[subject] = self._combine(group.op, values)
            leaves[subject] = tuple(leaf_vals)
        return list(universe), matched, leaves

    @staticmethod
    def _universe(children) -> List[str]:
        wild = set()
        for subjects, _m, _l in children:
            for s in subjects:
                if s != "-":
                    wild.add(s)
        return sorted(wild) if wild else ["-"]

    def _child_value(self, child, subject: str, node: ConditionNode):
        subjects, matched, leaves = child
        if isinstance(node, ConditionLeaf) and node.select.get("target") != "*":
            key = subjects[0] if subjects else "-"
            return matched.get(key), leaves.get(key, ())
        if subject in matched:
            return matched[subject], leaves.get(subject, ())
        return None, ()

    @staticmethod
    def _combine(op: str, values: List[Optional[bool]]) -> Optional[bool]:
        if op == "all":
            if any(v is False for v in values):
                return False
            if any(v is None for v in values):
                return None
            return True
        if any(v is True for v in values):
            return True
        if any(v is None for v in values):
            return None
        return False

    @staticmethod
    def _apply_no_data(matched: Optional[bool], no_data: str) -> Optional[bool]:
        if matched is not None:
            return matched
        if no_data == "ok":
            return False
        if no_data == "alerting":
            return True
        return None
