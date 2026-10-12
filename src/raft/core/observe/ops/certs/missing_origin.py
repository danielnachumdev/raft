"""Missing ``tls: origin`` PEM pair for one applied app."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MissingOriginCerts:
    app_name: str
    missing: tuple[str, ...]

    @property
    def detail(self) -> str:
        return f"missing {', '.join(self.missing)} under certs/{self.app_name}/"

    @property
    def fix(self) -> str:
        return (
            f"install Cloudflare Origin PEMs for {self.app_name} at "
            f"~/.raft/certs/{self.app_name}/origin.pem and origin.key "
            f"(required for tls: origin; then `raft gate recreate` if needed)"
        )
