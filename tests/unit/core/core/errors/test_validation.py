"""Settings/ports/wait/update validation CTAs and CTA helper smoke."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft.core.core.config.paths import RaftHome, raft_home
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import CtaFormatter, OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.port_list_parser import PortListParser
from raft.core.lifecycle.deploy.wait import WaitUntil
from raft.core.observe.ops.update import SelfUpdate

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.cta_asserts import CtaAsserts

SETTINGS_BAD_CASES = [
    ("edge:\n  http: eighty\n", "integer port"),
    ("- just a list\n", "YAML mapping"),
    ("logging:\n  level: NOPE\n", "logging.level"),
    ("edge:\n  streams:\n    - {name: s, port: nope}\n", "streams\\['s'\\].port"),
    ("{{{{invalid", "invalid YAML"),
]


class TestValidationCTAs(RaftTestCase):
    def test_empty_raft_data_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_DATA_HOME", "   ")
        with pytest.raises(OperatorError, match="RAFT_DATA_HOME"):
            RaftHome().resolve()

    def test_settings_bad_ports_and_shapes(self) -> None:
        path = self.tmp_path / "settings.yaml"
        for body, match in SETTINGS_BAD_CASES:
            path.write_text(body, encoding="utf-8")
            with pytest.raises(RuntimeError, match=match):
                SettingsLoader().load(self.tmp_path)
        bad_dir = self.tmp_path / "settings-as-dir"
        bad_dir.mkdir()
        with pytest.raises(RuntimeError, match="not a file"):
            SettingsLoader().load(self.tmp_path, path=bad_dir)

    def test_ports_require_int_and_bool(self) -> None:
        with pytest.raises(RuntimeError, match="containerPort"):
            PortListParser().parse(
                {"ports": [{"name": "http", "containerPort": "eighty", "expose": "http"}]},
                Path("app.yaml"),
            )
        with pytest.raises(RuntimeError, match="proxyProtocol"):
            PortListParser().parse(
                {
                    "ports": [
                        {
                            "name": "s",
                            "containerPort": 25,
                            "expose": "stream",
                            "publicPort": 25,
                            "proxyProtocol": "yes",
                        }
                    ]
                },
                Path("app.yaml"),
            )

    def test_wait_until_fix_cta(self) -> None:
        with pytest.raises(OperatorError) as caught:
            WaitUntil("never", lambda: False, timeout=0.05, interval=0.01, fix="retry").run()
        CtaAsserts.operator(caught.value, contains=("never",), fix_label="Fix: retry")

    def test_update_failure_cta(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, ())
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("curl failed")
        with pytest.raises(OperatorError) as caught:
            upd = SelfUpdate(stack)
            upd.sh = shell
            upd.run()
        CtaAsserts.operator(caught.value, contains=("raft update",))

    def test_settings_unreadable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        path = self.tmp_path / "settings.yaml"
        path.write_text("logging:\n  level: INFO\n", encoding="utf-8")
        monkeypatch.setattr(
            Path,
            "read_text",
            lambda self, *a, **k: (_ for _ in ()).throw(OSError("EACCES")),
        )
        with pytest.raises(RuntimeError, match="settings.yaml"):
            SettingsLoader().load(self.tmp_path)

    def test_cta_helpers_and_validation(self) -> None:
        assert CtaFormatter.subprocess_detail(RuntimeError("plain")) == "plain"
        formatted = CtaFormatter.format("head", ("step",), detail="plain detail")
        CtaAsserts.cta(formatted, contains=("plain detail", "step"))
        err = CtaFormatter.operator("headline", ("do this",), detail="more")
        CtaAsserts.operator(err, contains=("do this",))
        assert DomainErrors.require_bool(None, label="flag", default=True) is True
        assert DomainErrors.require_mapping({"a": 1}, label="doc") == {"a": 1}
        with pytest.raises(RuntimeError, match="YAML mapping"):
            DomainErrors.require_mapping([], label="doc", path="x.yaml")
