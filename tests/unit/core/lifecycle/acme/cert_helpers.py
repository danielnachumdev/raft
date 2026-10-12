"""Shared PEM helpers for ACME unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509.oid import NameOID


def _key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _validity(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if days >= 0:
        return now - timedelta(minutes=1), now + timedelta(days=days)
    not_after = now + timedelta(days=days)
    return not_after - timedelta(days=1), not_after


def _cert(key: RSAPrivateKey, names: list[str], *, days: int) -> x509.Certificate:
    not_before, not_after = _validity(days)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in names]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )


def self_signed_pem(names: list[str], *, days: int = 90) -> bytes:
    key = _key()
    return _cert(key, names, days=days).public_bytes(serialization.Encoding.PEM)


def plant_live_acme(home: Path, app: str, names: list[str], *, days: int) -> None:
    key = _key()
    d = home / "certs" / app
    d.mkdir(parents=True, exist_ok=True)
    (d / "acme.pem").write_bytes(_cert(key, names, days=days).public_bytes(serialization.Encoding.PEM))
    (d / "acme.key").write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
