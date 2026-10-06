"""On-disk layout for ``tls: acme`` live material and ACME account/webroot state."""

from __future__ import annotations

from pathlib import Path


class AcmePaths:
    """Resolve ``certs/<app>/acme.*`` and ``state/acme/`` under a data home."""

    def __init__(self, data_home: Path) -> None:
        self._root = data_home

    @property
    def state_dir(self) -> Path:
        return self._root / "state" / "acme"

    @property
    def http01_webroot(self) -> Path:
        return self.state_dir / "http-01"

    @property
    def apps_dir(self) -> Path:
        return self.state_dir / "apps"

    @property
    def account_key(self) -> Path:
        return self.state_dir / "account.key"

    @property
    def account_json(self) -> Path:
        return self.state_dir / "account.json"

    def app_state(self, app_name: str) -> Path:
        return self.apps_dir / f"{app_name}.json"

    def cert_files(self, app_name: str) -> tuple[Path, Path]:
        base = self._root / "certs" / app_name
        return (base / "acme.pem", base / "acme.key")

    def live_material_present(self, app_name: str) -> bool:
        pem, key = self.cert_files(app_name)
        return pem.is_file() and key.is_file()

    def ensure_dirs(self) -> None:
        for path in (self.state_dir, self.http01_webroot, self.apps_dir):
            path.mkdir(parents=True, exist_ok=True)

    def ensure_empty_app_state(self, app_name: str) -> Path:
        """Create ``state/acme/apps/<app>.json`` as ``{}`` when missing."""
        self.ensure_dirs()
        path = self.app_state(app_name)
        if not path.is_file():
            path.write_text("{}\n", encoding="utf-8")
        return path
