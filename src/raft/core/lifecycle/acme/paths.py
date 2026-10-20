"""On-disk layout for ``tls: acme`` live material and ACME account/webroot state."""

from pathlib import Path

from raft.core.core.config.paths.constants import HOST_ACME_DIR
from raft.core.core.config.paths.service_paths import ServicePaths


class AcmePaths:
    """Resolve ``services/<app>/certs/acme.*`` and ``host/acme/`` under a data home."""

    def __init__(self, data_home: Path) -> None:
        self._root = data_home

    @property
    def state_dir(self) -> Path:
        return self._root / HOST_ACME_DIR

    @property
    def http01_webroot(self) -> Path:
        return self.state_dir / "http-01"

    @property
    def account_key(self) -> Path:
        return self.state_dir / "account.key"

    @property
    def account_json(self) -> Path:
        return self.state_dir / "account.json"

    def app_state(self, app_name: str) -> Path:
        return ServicePaths(self._root, app_name).acme_state()

    def cert_files(self, app_name: str) -> tuple[Path, Path]:
        base = ServicePaths(self._root, app_name).certs()
        return (base / "acme.pem", base / "acme.key")

    def live_material_present(self, app_name: str) -> bool:
        pem, key = self.cert_files(app_name)
        return pem.is_file() and key.is_file()

    def ensure_dirs(self) -> None:
        for path in (self.state_dir, self.http01_webroot):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_empty_app_state(self, app_name: str) -> Path:
        """Create ``services/<app>/acme/state.json`` as ``{}`` when missing."""
        self.ensure_dirs()
        svc = ServicePaths(self._root, app_name)
        svc.acme().mkdir(parents=True, exist_ok=True)
        path = svc.acme_state()
        if not path.is_file():
            path.write_text("{}\n", encoding="utf-8")
        return path
