"""Shared catalog_entry payloads for rule kinds (keeps methods short)."""

from typing import Any, Dict, List

from raft.core.observe.notify.catalog_field import CatalogField

from .aggregates import Aggregates
from .operators import Comparison


def _threshold_aggregate_field() -> Dict[str, Any]:
    opts = [{"value": n, "label": n} for n in Aggregates.NAMES]
    return CatalogField.define(
        "aggregate",
        label="Aggregate",
        kind="select",
        required=True,
        options=opts,
        default="avg",
    )


def _threshold_window_field() -> Dict[str, Any]:
    return CatalogField.define(
        "window",
        label="Window",
        kind="duration",
        required=True,
        default="5m",
    )


def _comparison_op_field(*, default: str) -> Dict[str, Any]:
    opts = [{"value": o, "label": o} for o in Comparison.OPS]
    return CatalogField.define(
        "op",
        label="Operator",
        kind="select",
        required=True,
        options=opts,
        default=default,
    )


def _number_field(name: str, *, label: str, default: Any = None) -> Dict[str, Any]:
    kw: Dict[str, Any] = {"label": label, "kind": "number", "required": True}
    if default is not None:
        kw["default"] = default
    return CatalogField.define(name, **kw)


def threshold_catalog(kind_id: str) -> dict:
    return {
        "kind_id": kind_id,
        "label": "Threshold",
        "value_types": ["numeric"],
        "fields": [
            _threshold_aggregate_field(),
            _threshold_window_field(),
            _comparison_op_field(default="gt"),
            _number_field("value", label="Value"),
        ],
    }


def event_count_catalog(kind_id: str) -> dict:
    return {
        "kind_id": kind_id,
        "label": "Event count",
        "value_types": ["event"],
        "fields": [
            CatalogField.define(
                "window", label="Window", kind="duration", required=True, default="1h"
            ),
            _comparison_op_field(default="gte"),
            _number_field("value", label="Count", default=1),
        ],
    }


def _state_match_field() -> Dict[str, Any]:
    return CatalogField.define(
        "match",
        label="Match",
        kind="select",
        required=True,
        options=[
            {"value": "in", "label": "In"},
            {"value": "notIn", "label": "Not in"},
        ],
        default="notIn",
    )


def state_match_catalog(kind_id: str) -> dict:
    return {
        "kind_id": kind_id,
        "label": "State match",
        "value_types": ["state"],
        "fields": [
            _state_match_field(),
            CatalogField.define(
                "values",
                label="Values",
                kind="string_list",
                required=True,
                default="running",
            ),
        ],
    }
