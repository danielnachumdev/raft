"""Per-service durable paths under ``RAFT_DATA_HOME/services/<name>/`` (#313)."""

from pathlib import Path

from .constants import (
    ACME_DIRNAME,
    ACME_STATE_FILENAME,
    APP_MANIFEST_FILENAME,
    CERTS_DIRNAME,
    CHECKOUT_DIRNAME,
    DEPLOY_DIRNAME,
    LOGS_DIRNAME,
    SCALING_DIRNAME,
    SCALING_STATE_FILENAME,
    SECRETS_DIRNAME,
    SERVICES_DIRNAME,
)


class ServicePaths:
    """App-owned durable paths for one applied service name."""

    def __init__(self, home: Path, name: str) -> None:
        self._home = home
        self._name = name

    def root(self) -> Path:
        return self._home / SERVICES_DIRNAME / self._name

    def app_yaml(self) -> Path:
        return self.root() / APP_MANIFEST_FILENAME

    def secrets(self) -> Path:
        return self.root() / SECRETS_DIRNAME

    def secrets_env(self) -> Path:
        return self.secrets() / "env"

    def certs(self) -> Path:
        return self.root() / CERTS_DIRNAME

    def checkout(self) -> Path:
        return self.root() / CHECKOUT_DIRNAME

    def deploy(self) -> Path:
        return self.root() / DEPLOY_DIRNAME

    def deploy_ref(self) -> Path:
        return self.deploy() / f"{self._name}.ref"

    def deploy_image(self) -> Path:
        return self.deploy() / f"{self._name}.image"

    def scaling(self) -> Path:
        return self.root() / SCALING_DIRNAME

    def scaling_state(self) -> Path:
        return self.scaling() / SCALING_STATE_FILENAME

    def scaling_markers(self) -> Path:
        return self.scaling() / "markers"

    def logs(self) -> Path:
        return self.root() / LOGS_DIRNAME

    def acme(self) -> Path:
        return self.root() / ACME_DIRNAME

    def acme_state(self) -> Path:
        return self.acme() / ACME_STATE_FILENAME

    def ensure_scaffold(self) -> Path:
        root = self.root()
        for path in (
            root,
            self.secrets(),
            self.certs(),
            self.checkout(),
            self.deploy(),
            self.scaling(),
            self.scaling_markers(),
            self.logs(),
            self.acme(),
        ):
            path.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def default_checkout_rel(name: str) -> str:
        return f"{SERVICES_DIRNAME}/{name}/{CHECKOUT_DIRNAME}"
