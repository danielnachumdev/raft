"""AcmeAccountStore load/create and registration persistence."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from acme import messages

from raft.acme.account import AcmeAccountStore
from raft.acme.paths import AcmePaths

from tests.unit.base import RaftTestCase


class TestAcmeAccountStore(RaftTestCase):
    def _run(self, store: AcmeAccountStore, fake: MagicMock, **kwargs):
        mock_cls = MagicMock(return_value=fake)
        mock_cls.get_directory.return_value = MagicMock()
        net = MagicMock()
        with patch("raft.acme.account.client.ClientNetwork", return_value=net):
            with patch("raft.acme.account.client.ClientV2", mock_cls):
                return store.client_for(**kwargs), net

    def _fake_regr(self, uri: str) -> MagicMock:
        regr = MagicMock()
        regr.uri = uri
        regr.body.to_json.return_value = {"status": "valid", "contact": []}
        return regr

    def test_creates_key_and_registers(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        fake = MagicMock()
        fake.new_account.return_value = self._fake_regr("https://acme.example/acct/1")
        client, net = self._run(
            store, fake, directory_url="https://acme.example/directory", email="ops@x.com"
        )
        assert client is fake
        assert AcmePaths(self.tmp_path).account_key.is_file()
        assert net.account.uri.endswith("/acct/1")

    def test_reuses_saved_registration(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        store._load_or_create_key()
        body = messages.Registration.from_json({"status": "valid"}).to_json()
        self._write_account("https://acme.example/directory", "https://acme.example/acct/1", body)
        fake = MagicMock()
        _c, net = self._run(
            store, fake, directory_url="https://acme.example/directory", email="ops@x.com"
        )
        fake.new_account.assert_not_called()
        assert net.account.uri.endswith("/acct/1")

    def test_directory_mismatch_reregisters(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        store._load_or_create_key()
        self._write_account("https://old.example/dir", "https://old.example/acct/1", {"status": "valid"})
        fake = MagicMock()
        fake.new_account.return_value = self._fake_regr("https://new.example/acct/2")
        self._run(store, fake, directory_url="https://new.example/dir", email="ops@x.com")
        fake.new_account.assert_called_once()

    def test_corrupt_account_json_reregisters(self) -> None:
        store = AcmeAccountStore(self.tmp_path)
        store._load_or_create_key()
        AcmePaths(self.tmp_path).account_json.write_text("not-json\n", encoding="utf-8")
        fake = MagicMock()
        fake.new_account.return_value = self._fake_regr("https://acme.example/acct/9")
        self._run(store, fake, directory_url="https://acme.example/dir", email="ops@x.com")
        fake.new_account.assert_called_once()

    def _write_account(self, directory: str, uri: str, body) -> None:
        AcmePaths(self.tmp_path).account_json.write_text(
            json.dumps({"directory": directory, "uri": uri, "body": body}) + "\n",
            encoding="utf-8",
        )
