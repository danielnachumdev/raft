"""CSR / PEM helpers for ``tls: acme`` live material (cryptography)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtensionOID, NameOID


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
            ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        except x509.ExtensionNotFound:
            return ()
        return tuple(ext.value.get_values_for_type(x509.DNSName))

    def not_after_iso(self) -> str:
        return self.not_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def days_until_expiry(self, *, now: datetime | None = None) -> float:
        when = now if now is not None else datetime.now(timezone.utc)
        return (self.not_after - when).total_seconds() / 86400.0


class AcmeCertWriter:
    """Generate CSR/key and install fullchain + key under ``certs/<app>/``."""

    def generate_key_and_csr(self, names: Sequence[str]) -> tuple[bytes, bytes]:
        if not names:
            raise ValueError("ACME CSR requires at least one DNS name")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])])
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(n) for n in names]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return key_pem, csr.public_bytes(serialization.Encoding.PEM)

    def install(self, pem_path: Path, key_path: Path, *, fullchain_pem: bytes, key_pem: bytes) -> None:
        pem_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(pem_path, fullchain_pem)
        self._atomic_write(key_path, key_pem)

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def parse_installed(self, pem_path: Path) -> AcmeCertMaterial:
        return AcmeCertMaterial.from_pem(pem_path.read_bytes())
