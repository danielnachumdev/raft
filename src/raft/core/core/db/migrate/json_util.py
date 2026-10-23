"""JSON helpers for migrate-from-files (PII-safe; no secrets transformation)."""

import json
from typing import Any


class MigrateJson:
    """Serialize YAML-loaded mappings to JSON text for DB payload columns."""

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, sort_keys=True, default=str)

    @staticmethod
    def loads(text: str) -> Any:
        return json.loads(text)
