"""CLI rendering helpers for ``raft alerts``."""

from typing import Any, Dict, List, Optional

import yaml

from raft.core.core.ui import OperatorSay


class AlertsCliOutput:
    """Tables / json / yaml for alert CLI commands."""

    def list_table(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            OperatorSay.say(
                "No alert rules. Add one with `raft alerts apply --file …` "
                "or Settings → Alerts in `raft serve`."
            )
            return
        OperatorSay.say("ID  ENABLED  SEVERITY  STATE  CONDITION")
        for row in rows:
            OperatorSay.say(
                f"{row['id']}  {row['enabled']}  {row['severity']}  "
                f"{row['state']}  {row['condition']}"
            )

    def say_yaml(self, payload: Dict[str, Any]) -> None:
        OperatorSay.say(yaml.safe_dump(payload, sort_keys=False))

    def say_json(self, payload: Any) -> None:
        import json

        OperatorSay.say(json.dumps(payload, indent=2, sort_keys=False))

    def say(self, message: str) -> None:
        OperatorSay.say(message)

    def say_err(self, message: str) -> None:
        OperatorSay.say_err(message)

    def print_validation(self, report: Dict[str, Any]) -> None:
        if report.get("ok"):
            n = report.get("ruleCount", 0)
            OperatorSay.say(f"OK ({n} rules)")
        for err in report.get("errors") or []:
            OperatorSay.say_err(f"{err['path']}: {err['message']}")
        for warn in report.get("warnings") or []:
            OperatorSay.say(f"warning: {warn['path']}: {warn['message']}")

    def print_dry_run(self, report: Dict[str, Any]) -> None:
        if report.get("error"):
            OperatorSay.say_err(report["error"])
        for subject in report.get("subjects") or []:
            OperatorSay.say(
                f"{subject['subject']}: matched={subject['matched']} "
                f"{subject['currentState']} → {subject['wouldState']} "
                f"notify={subject.get('wouldNotify') or '—'}"
            )
            for leaf in subject.get("leaves") or []:
                OperatorSay.say(f"  {leaf.get('detail')}")

    def print_deliveries(self, deliveries: List[Any]) -> None:
        for item in deliveries:
            status = item.result.status.value
            err = item.result.error or ""
            OperatorSay.say(
                f"{item.channel_id}  {item.type_id}  {status}  {err}".rstrip()
            )

    def recommendations_table(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            OperatorSay.say("No open alert recommendations.")
            return
        OperatorSay.say("ID  KIND  TITLE")
        for item in items:
            OperatorSay.say(
                f"{item.get('id')}  {item.get('kind')}  {item.get('title')}"
            )
