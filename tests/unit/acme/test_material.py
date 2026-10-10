"""AcmeCertMaterial / AcmeCertWriter helpers."""

from __future__ import annotations

import pytest

from raft.acme.material import AcmeCertMaterial, AcmeCertWriter

from .cert_helpers import self_signed_pem
from tests.unit.base import RaftTestCase


class TestAcmeCertMaterial(RaftTestCase):
    def test_parse_and_days(self) -> None:
        pem = self_signed_pem(["a.test", "b.test"], days=60)
        material = AcmeCertMaterial.from_pem(pem)
        assert material.names == ("a.test", "b.test")
        assert material.days_until_expiry() > 50
        assert "T" in material.not_after_iso()

    def test_writer_csr_and_install(self) -> None:
        writer = AcmeCertWriter()
        key_pem, csr_pem = writer.generate_key_and_csr(["x.test"])
        assert b"PRIVATE KEY" in key_pem or b"RSA PRIVATE KEY" in key_pem
        assert b"CERTIFICATE REQUEST" in csr_pem
        pem_path = self.tmp_path / "acme.pem"
        key_path = self.tmp_path / "acme.key"
        writer.install(pem_path, key_path, fullchain_pem=self_signed_pem(["x.test"]), key_pem=key_pem)
        assert writer.parse_installed(pem_path).names == ("x.test",)

    def test_csr_requires_names(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            AcmeCertWriter().generate_key_and_csr([])
