"""Typed settings-field metadata for serve strategy catalog / SPA forms."""

from typing import Any, Dict, List, Optional


class CatalogField:
    """One operator-facing settings key declared by a NotificationStrategy."""

    @staticmethod
    def define(
        key: str,
        *,
        label: str,
        kind: str = "text",
        required: bool = False,
        help_text: str = "",
        placeholder: str = "",
        options: Optional[List[Dict[str, str]]] = None,
        default: Any = None,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "key": key,
            "label": label,
            "kind": kind,
            "required": required,
        }
        CatalogField._optional(row, "help", help_text)
        CatalogField._optional(row, "placeholder", placeholder)
        if options is not None:
            row["options"] = list(options)
        if default is not None:
            row["default"] = default
        return row

    @staticmethod
    def _optional(row: Dict[str, Any], name: str, value: str) -> None:
        if value:
            row[name] = value

    @staticmethod
    def entry(
        type_id: str,
        *,
        label: str,
        fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "type_id": type_id,
            "label": label,
            "fields": list(fields or []),
        }
