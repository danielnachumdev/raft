"""Doctor skeleton when ``tls: acme`` live material is not on disk yet."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MissingAcmeCerts:
    """Doctor skeleton when ``tls: acme`` live material is not on disk yet."""

    app_name: str
    missing: tuple[str, ...]

    @property
    def detail(self) -> str:
        return f"missing {', '.join(self.missing)} under certs/{self.app_name}/"

    @property
    def fix(self) -> str:
        return (
            f"point DNS A/AAAA for {self.app_name} publicHost (+ extraHosts) at this host; "
            f"keep edge.http (:80) and edge.https (:443) published; set acme.email in "
            f"~/.raft/host/settings.yaml; then re-apply so ACME can issue "
            f"~/.raft/services/*/certs/{self.app_name}/acme.pem and acme.key "
            f"(do not paste Origin PEMs for tls: acme)"
        )
