"""Directory and filename constants for the raft data home (#313)."""

from pathlib import Path

DATA_HOME_ENV = "RAFT_DATA_HOME"
SETTINGS_FILENAME = "settings.yaml"
FIREWALL_FILENAME = "firewall.yaml"
ALERTS_FILENAME = "alerts.yaml"
NOTIFICATIONS_FILENAME = "notifications.yaml"
RBAC_FILENAME = "rbac.yaml"
DB_FILENAME = "raft.sqlite"
GENERATED_DIRNAME = "generated"
HOST_DIRNAME = "host"
SERVICES_DIRNAME = "services"
CHECKOUT_DIRNAME = "checkout"
DEPLOY_DIRNAME = "deploy"
CERTS_DIRNAME = "certs"
LOGS_DIRNAME = "logs"
SECRETS_DIRNAME = "secrets"
SCALING_DIRNAME = "scaling"
ACME_DIRNAME = "acme"
APP_MANIFEST_FILENAME = "app.yaml"
SCALING_STATE_FILENAME = "state.json"
MANUAL_STOP_FILENAME = "manual-stop"
ACME_STATE_FILENAME = "state.json"

# Export alias used by checkout path helpers.
APPS_DIRNAME = CHECKOUT_DIRNAME

HOST_DIR = Path(HOST_DIRNAME)
SERVICES_DIR = Path(SERVICES_DIRNAME)
SETTINGS_REL = HOST_DIR / SETTINGS_FILENAME
FIREWALL_REL = HOST_DIR / FIREWALL_FILENAME
ALERTS_REL = HOST_DIR / ALERTS_FILENAME
NOTIFICATIONS_REL = HOST_DIR / NOTIFICATIONS_FILENAME
RBAC_REL = HOST_DIR / RBAC_FILENAME
LOCKS_DIR = HOST_DIR / "locks"
STATE_DIR = SERVICES_DIR  # applied Apps live under services/<name>/app.yaml
HOST_LOGS_DIR = HOST_DIR / LOGS_DIRNAME
HOST_SECRETS_DIR = HOST_DIR / SECRETS_DIRNAME
HOST_ALERTS_DIR = HOST_DIR / "alerts"
HOST_INBOX_DIR = HOST_DIR / "inbox"
HOST_EVENTS_DIR = HOST_DIR / "events"
HOST_METRICS_DIR = HOST_DIR / "metrics"
HOST_ACME_DIR = HOST_DIR / ACME_DIRNAME
HOST_SERVE_DIR = HOST_DIR / "serve"
HOST_DB_DIR = HOST_DIR / "db"
HOST_EDGE_SERVICE_LOGS_DIR = HOST_LOGS_DIR / "services"
GATE_NGINX_FINGERPRINT = HOST_DIR / "gate-nginx.fingerprint"
ROUTER_NGINX_FINGERPRINT = HOST_DIR / "router-nginx.fingerprint"

DATA_DIR_RELS = (
    GENERATED_DIRNAME,
    HOST_DIRNAME,
    str(LOCKS_DIR),
    str(HOST_ALERTS_DIR),
    str(HOST_INBOX_DIR),
    str(HOST_EVENTS_DIR),
    str(HOST_METRICS_DIR),
    str(HOST_METRICS_DIR / "gate-http"),
    str(HOST_ACME_DIR),
    str(HOST_ACME_DIR / "http-01"),
    str(HOST_SERVE_DIR),
    str(HOST_DB_DIR),
    str(HOST_SECRETS_DIR / "dashboard"),
    str(HOST_LOGS_DIR),
    str(HOST_EDGE_SERVICE_LOGS_DIR),
    SERVICES_DIRNAME,
    f"{GENERATED_DIRNAME}/nginx/gate-tls",
    f"{GENERATED_DIRNAME}/nginx/gate-http",
    f"{GENERATED_DIRNAME}/nginx/gate-stream",
    f"{GENERATED_DIRNAME}/nginx/router",
    f"{GENERATED_DIRNAME}/nginx/upstreams",
)

TEMPLATE_FILES = ("compose.yaml",)
TEMPLATE_DIRS = ("nginx", "controller", "dashboard")
CONTROLLER_BUILD_DIR = "controller"
DASHBOARD_BUILD_DIR = "dashboard"
CONTROLLER_PACKAGE_DIR = "raft"
CONTROLLER_PYPROJECT = "pyproject.toml"
