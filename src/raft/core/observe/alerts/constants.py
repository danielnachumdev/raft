"""Alert engine constants and limits."""

from pathlib import Path

KIND_ALERT_FIRING = "alert.firing"
KIND_ALERT_RESOLVED = "alert.resolved"
KIND_ALERT_TEST = "alert.test"

ALERTS_STATE_DIR = Path("host") / "alerts"
RULES_NAME = "rules.yaml"
RUNTIME_NAME = "runtime.json"
DISMISSALS_NAME = "dismissed-recommendations.json"

MAX_RULES = 200
MAX_LEAVES = 8
MAX_DEPTH = 3
MAX_WINDOW_SECONDS = 86400
MAX_COOLDOWN_SECONDS = 7 * 86400
MAX_FOR_SECONDS = 86400
MAX_NAME_LEN = 120
MAX_DESCRIPTION_LEN = 500
MAX_ERRORS = 50
RULE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
DOCUMENT_VERSION = 1
