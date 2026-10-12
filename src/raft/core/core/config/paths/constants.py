"""Directory and filename constants for the raft data home."""

from pathlib import Path

from raft.core.platform.secrets import SECRETS_DIRNAME

DATA_HOME_ENV = "RAFT_DATA_HOME"
SETTINGS_FILENAME = "settings.yaml"
GENERATED_DIRNAME = "generated"
DEPLOY_DIRNAME = "deploy"
APPS_DIRNAME = "apps"
CERTS_DIRNAME = "certs"
LOGS_DIRNAME = "logs"
STATE_DIR = Path("state") / "apps"
LOCKS_DIR = Path("state") / "locks"

DATA_DIR_RELS = (
    GENERATED_DIRNAME,
    DEPLOY_DIRNAME,
    APPS_DIRNAME,
    CERTS_DIRNAME,
    LOGS_DIRNAME,
    SECRETS_DIRNAME,
    str(STATE_DIR),
    str(LOCKS_DIR),
    "state/scaling",
    "state/scaling/markers",
    "state/metrics",
    "state/metrics/gate-http",
    "state/events",
    "state/serve",
    "state/acme",
    "state/acme/http-01",
    "state/acme/apps",
    f"{GENERATED_DIRNAME}/nginx/gate-tls",
    f"{GENERATED_DIRNAME}/nginx/gate-http",
    f"{GENERATED_DIRNAME}/nginx/gate-stream",
    f"{GENERATED_DIRNAME}/nginx/router",
    f"{GENERATED_DIRNAME}/nginx/upstreams",
)

TEMPLATE_FILES = ("compose.yaml",)
TEMPLATE_DIRS = ("nginx", "controller")
CONTROLLER_BUILD_DIR = "controller"
CONTROLLER_PACKAGE_DIR = "raft"
CONTROLLER_PYPROJECT = "pyproject.toml"
