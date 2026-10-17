"""Serve/CLI form catalog for alert rules."""

from typing import Any, Dict, List, Sequence

from raft.core.observe.notify.catalog_field import CatalogField

from ..constants import MAX_DEPTH, MAX_LEAVES, MAX_RULES
from ..registries import AlertRegistries


class AlertCatalog:
    """Build dynamic catalog JSON for forms."""

    @staticmethod
    def build(
        registries: AlertRegistries,
        app_names: Sequence[str],
        channels: Sequence[str] = (),
    ) -> Dict[str, Any]:
        sources = []
        for entry in registries.signals.catalog():
            sources.append(AlertCatalog._with_targets(entry, app_names))
        return {
            "sources": sources,
            "kinds": registries.kinds.catalog(),
            "severities": ["info", "warning", "error", "critical"],
            "noData": ["ok", "alerting", "keep"],
            "limits": {
                "maxRules": MAX_RULES,
                "maxLeaves": MAX_LEAVES,
                "maxDepth": MAX_DEPTH,
            },
        }

    @staticmethod
    def _with_targets(entry: Dict[str, Any], app_names: Sequence[str]) -> Dict[str, Any]:
        type_id = entry.get("type_id", "")
        options = AlertCatalog._target_options(type_id, app_names)
        fields = []
        for field in entry.get("select_fields") or []:
            if field.get("key") == "target":
                field = {**field, "options": options}
            fields.append(field)
        return {**entry, "select_fields": fields}

    @staticmethod
    def _target_options(type_id: str, app_names: Sequence[str]) -> List[Dict[str, str]]:
        opts: List[Dict[str, str]] = []
        if type_id == "metrics.resources":
            opts.append({"value": "host", "label": "Host"})
        if type_id == "metrics.http":
            opts.append({"value": "edge", "label": "Edge (all traffic)"})
        opts.append({"value": "*", "label": "Each app"})
        if type_id == "control.events":
            opts.append({"value": "-", "label": "Stack (no service)"})
        for name in app_names:
            opts.append({"value": name, "label": name})
        return opts
