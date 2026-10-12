"""Parsed live certificate metadata for ``tls: acme``."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.x509.oid import ExtensionOID


@dataclass(frozen=True)
class AcmeCertMaterial:
    """Parsed live certificate (notAfter + SANs)."""

    not_after: datetime
    names: tuple[str, ...]

    @classmethod
    def from_pem(cls, pem: bytes) -> "AcmeCertMaterial":
        cert = x509.load_pem_x509_certificate(pem)
        not_after = cert.not_valid_after_utc
        return cls(not_after=not_after, names=cls._sans(cert))

    @staticmethod
    def _sans(cert: x509.Certificate) -> tuple[str, ...]:
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
        except x509.ExtensionNotFound:
            return ()
        return tuple(ext.value.get_values_for_type(x509.DNSName))

    def not_after_iso(self) -> str:
        return self.not_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def days_until_expiry(self, *, now: Optional[datetime] = None) -> float:
        when = now if now is not None else datetime.now(timezone.utc)
        return (self.not_after - when).total_seconds() / 86400.0
