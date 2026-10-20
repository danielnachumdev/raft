"""Directory and filename constants for the raft data home (#313)."""

from pathlib import Path

DATA_HOME_ENV = "RAFT_DATA_HOME"
SETTINGS_FILENAME = "settings.yaml"
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
ACME_STATE_FILENAME = "state.json"

# Legacy export aliases (checkout path segment used to be top-level ``apps/``).
APPS_DIRNAME = CHECKOUT_DIRNAME

HOST_DIR = Path(HOST_DIRNAME)
SERVICES_DIR = Path(SERVICES_DIRNAME)
SETTINGS_REL = HOST_DIR / SETTINGS_FILENAME
LOCKS_DIR = HOST_DIR / "locks"
STATE_DIR = SERVICES_DIR  # applied Apps live under services/<name>/app.yaml
HOST_LOGS_DIR = HOST_DIR / LOGS_DIRNAME
HOST_SECRETS_DIR = HOST_DIR / SECRETS_DIRNAME
HOST_FIREWALL_DIR = HOST_DIR / "firewall"
HOST_ALERTS_DIR = HOST_DIR / "alerts"
HOST_EVENTS_DIR = HOST_DIR / "events"
HOST_METRICS_DIR = HOST_DIR / "metrics"
HOST_ACME_DIR = HOST_DIR / ACME_DIRNAME
HOST_SERVE_DIR = HOST_DIR / "serve"
HOST_EDGE_SERVICE_LOGS_DIR = HOST_LOGS_DIR / "services"
GATE_NGINX_FINGERPRINT = HOST_DIR / "gate-nginx.fingerprint"
ROUTER_NGINX_FINGERPRINT = HOST_DIR / "router-nginx.fingerprint"

DATA_DIR_RELS = (
    GENERATED_DIRNAME,
    HOST_DIRNAME,
    str(LOCKS_DIR),
    str(HOST_FIREWALL_DIR),
    str(HOST_ALERTS_DIR),
    str(HOST_EVENTS_DIR),
    str(HOST_METRICS_DIR),
    str(HOST_METRICS_DIR / "gate-http"),
    str(HOST_ACME_DIR),
    str(HOST_ACME_DIR / "http-01"),
    str(HOST_SERVE_DIR),
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

# Old layout roots doctor treats as unmigrated (#313).
OLD_LAYOUT_MARKERS = (
    Path("state") / "apps",
    Path("settings.yaml"),
    Path("secrets"),
    Path("certs"),
    Path("apps"),
    Path("deploy"),
    Path("logs"),
    Path("state") / "locks",
    Path("state") / "firewall",
    Path("state") / "alerts",
    Path("state") / "events",
    Path("state") / "metrics",
    Path("state") / "scaling",
    Path("state") / "service-logs",
    Path("state") / "serve",
    Path("state") / "acme",
)

TEMPLATE_FILES = ("compose.yaml",)
TEMPLATE_DIRS = ("nginx", "controller", "dashboard")
CONTROLLER_BUILD_DIR = "controller"
DASHBOARD_BUILD_DIR = "dashboard"
CONTROLLER_PACKAGE_DIR = "raft"
CONTROLLER_PYPROJECT = "pyproject.toml"
