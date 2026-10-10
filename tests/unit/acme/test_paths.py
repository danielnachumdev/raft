"""AcmePaths layout helpers."""

from __future__ import annotations

from raft.acme.paths import AcmePaths

from tests.unit.base import RaftTestCase


class TestAcmePaths(RaftTestCase):
    def test_cert_files_and_live_material(self) -> None:
        paths = AcmePaths(self.tmp_path)
        pem, key = paths.cert_files("web")
        assert pem.name == "acme.pem"
        assert key.name == "acme.key"
        assert paths.live_material_present("web") is False
        pem.parent.mkdir(parents=True)
        pem.write_text("pem\n", encoding="utf-8")
        key.write_text("key\n", encoding="utf-8")
        assert paths.live_material_present("web") is True

    def test_ensure_dirs_and_empty_app_state(self) -> None:
        paths = AcmePaths(self.tmp_path)
        state = paths.ensure_empty_app_state("web")
        assert state.is_file()
        assert state.read_text(encoding="utf-8") == "{}\n"
        assert paths.http01_webroot.is_dir()
        assert paths.account_key.name == "account.key"
        assert paths.account_json.name == "account.json"
        again = paths.ensure_empty_app_state("web")
        assert again == state
