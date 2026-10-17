"""CLI rendering helpers for ``raft firewall``."""

from typing import Any, Dict, List, Optional

import json
import yaml

from raft.core.core.ui import OperatorSay


class FirewallCliOutput:
    """Tables / json / yaml for firewall CLI commands."""

    def say(self, message: str) -> None:
        OperatorSay.say(message)

    def say_yaml(self, payload: Any) -> None:
        OperatorSay.say(yaml.safe_dump(payload, sort_keys=False).rstrip())

    def say_json(self, payload: Any) -> None:
        OperatorSay.say(json.dumps(payload, indent=2, sort_keys=False))

    def emit(self, payload: Any, *, as_json: bool) -> None:
        if as_json:
            self.say_json(payload)
            return
        self.say_yaml(payload)

    def rules_table(self, rules: List[Dict[str, Any]]) -> None:
        if not rules:
            OperatorSay.say(
                "No firewall rules. Add with `raft firewall replace --file …` "
                "or Settings → Firewall in `raft serve`."
            )
            return
        OperatorSay.say("ID  CIDR  PORT  PROTO  SERVICE  ACTION")
        for rule in rules:
            OperatorSay.say(
                f"{rule.get('id')}  {rule.get('cidr')}  {rule.get('port')}  "
                f"{rule.get('protocol')}  {rule.get('service')}  "
                f"{rule.get('action')}"
            )

    def recommendations_table(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            OperatorSay.say("No open firewall recommendations.")
            return
        OperatorSay.say("ID  KIND  TITLE")
        for item in items:
            OperatorSay.say(
                f"{item.get('id')}  {item.get('kind')}  {item.get('title')}"
            )

    def services_table(self, services: List[Dict[str, Any]]) -> None:
        OperatorSay.say("NAME  LABEL/HOST")
        for item in services:
            label = item.get("label") or item.get("publicHost") or ""
            OperatorSay.say(f"{item.get('name')}  {label}")

    def write_file(self, path: str, text: str) -> None:
        from pathlib import Path

        Path(path).write_text(text, encoding="utf-8")
        OperatorSay.say(f"Wrote {path}")

    def applied(self, result: Dict[str, Any], *, note: Optional[str] = None) -> None:
        n = len(result.get("rules") or [])
        msg = note or f"Applied firewall document ({n} rules); gate nginx reloaded if running."
        OperatorSay.say(msg)
