"""CLI rendering helpers for ``raft notifications``."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from raft.core.core.ui import OperatorSay


class NotificationsCliOutput:
    """Tables / json for notification CLI commands."""

    def list_table(self, channels: List[Dict[str, Any]], *, enabled: bool) -> None:
        if not channels:
            OperatorSay.say(
                "No notification channels. Add one with "
                "`raft notifications create --file …` "
                "or Settings → Notifications in `raft serve`."
            )
            return
        OperatorSay.say(
            f"Global notifications: {'on' if enabled else 'off'}"
        )
        OperatorSay.say("ID  ENABLED  TYPE")
        for row in channels:
            OperatorSay.say(
                f"{row['id']}  {row['enabled']}  {row['type']}"
            )

    def strategies_table(self, strategies: List[Dict[str, Any]]) -> None:
        if not strategies:
            OperatorSay.say("No notification strategies registered.")
            return
        OperatorSay.say("TYPE_ID  LABEL")
        for row in strategies:
            label = (row.get("label") or "").strip() or row.get("type_id", "")
            OperatorSay.say(f"{row.get('type_id')}  {label}")

    def print_deliveries(self, deliveries: List[Any]) -> None:
        for item in deliveries:
            status = item.result.status.value
            err = item.result.error or ""
            OperatorSay.say(
                f"{item.channel_id}  {item.type_id}  {status}  {err}".rstrip()
            )

    def say_yaml(self, payload: Dict[str, Any]) -> None:
        OperatorSay.say(yaml.safe_dump(payload, sort_keys=False).rstrip())

    def say_json(self, payload: Any) -> None:
        import json

        OperatorSay.say(json.dumps(payload, indent=2, sort_keys=False))

    def say(self, message: str) -> None:
        OperatorSay.say(message)

    def write_file(self, path: str, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")
        OperatorSay.say(f"Wrote {path}")
