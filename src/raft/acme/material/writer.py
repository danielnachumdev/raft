"""CSR / key generation and install of live ``acme.{pem,key}`` bytes."""

from pathlib import Path
from typing import Sequence

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .material import AcmeCertMaterial


class AcmeCertWriter:
    """Generate CSR/key and install fullchain + key under ``certs/<app>/``."""

    def generate_key_and_csr(self, names: Sequence[str]) -> tuple[bytes, bytes]:
        if not names:
            raise ValueError("ACME CSR requires at least one DNS name")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = self._build_csr(key, names)
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return key_pem, csr.public_bytes(serialization.Encoding.PEM)

    @staticmethod
    def _build_csr(key: rsa.RSAPrivateKey, names: Sequence[str]) -> x509.CertificateSigningRequest:
        return (
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

    def install(
        self,
        pem_path: Path,
        key_path: Path,
        *,
        fullchain_pem: bytes,
        key_pem: bytes,
    ) -> None:
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
