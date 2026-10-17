"""Shared catalog_entry payloads for signal sources."""

from typing import Any, Dict, List, Sequence

from raft.core.observe.notify.catalog_field import CatalogField


def _target_field() -> Dict[str, Any]:
    return CatalogField.define(
        "target", label="Target", kind="select", required=True
    )


def _metric_field() -> Dict[str, Any]:
    return CatalogField.define(
        "metric", label="Metric", kind="select", required=True
    )


def _metric_rows(metrics: Sequence[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "key": m.key,
            "label": m.label,
            "unit": m.unit,
            "scopes": list(m.scopes),
        }
        for m in metrics
    ]


def metric_source_catalog(
    *,
    type_id: str,
    label: str,
    metrics: Sequence[Any],
) -> Dict[str, Any]:
    return {
        "type_id": type_id,
        "label": label,
        "value_type": "numeric",
        "select_fields": [_target_field(), _metric_field()],
        "metrics": _metric_rows(metrics),
    }


def container_status_catalog(type_id: str) -> Dict[str, Any]:
    return {
        "type_id": type_id,
        "label": "Container status",
        "value_type": "state",
        "select_fields": [_target_field()],
        "metrics": [],
    }


_EVENT_KINDS = (
    "deployment",
    "stop",
    "start",
    "scaling",
    "up",
    "down",
    "update",
    "gate_recreate",
)


def _event_kind_field() -> Dict[str, Any]:
    opts = [{"value": k, "label": k} for k in _EVENT_KINDS]
    return CatalogField.define(
        "eventKind",
        label="Event kind",
        kind="select",
        required=True,
        options=opts,
    )


def graph_events_catalog(type_id: str) -> Dict[str, Any]:
    return {
        "type_id": type_id,
        "label": "Lifecycle events",
        "value_type": "event",
        "select_fields": [
            _target_field(),
            _event_kind_field(),
            CatalogField.define(
                "action", label="Action", kind="text", required=False
            ),
        ],
        "metrics": [],
    }
