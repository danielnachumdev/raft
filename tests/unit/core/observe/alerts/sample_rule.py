"""PII-safe sample alert rules for unit tests."""

RULE = {
    "id": "demo-api-5xx-rate",
    "name": "demo-api 5xx",
    "severity": "error",
    "for": "0s",
    "cooldown": "15m",
    "condition": {
        "signal": "metrics.http",
        "select": {"target": "demo-api", "metric": "error_rate_5xx"},
        "kind": "threshold",
        "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0.05},
    },
}

OTHER = {
    **RULE,
    "id": "demo-web-cpu",
    "name": "cpu",
    "condition": {
        "signal": "metrics.resources",
        "select": {"target": "demo-web", "metric": "cpu_percent"},
        "kind": "threshold",
        "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 85},
    },
}
