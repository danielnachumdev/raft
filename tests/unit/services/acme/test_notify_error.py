"""AcmeEnsure notifies on lastError persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.config.settings_types import AcmeConfig
from raft.models.stack import load_stack
from raft.services.acme.ensure import AcmeEnsure
from raft.services.notify.control_events import KIND_ACME_ERROR

from ...base import RaftTestCase, write_applied_app


class TestAcmeNotifyError(RaftTestCase):
    def test_missing_email_notifies(self) -> None:
        write_applied_app(
            self.tmp_path, "demo-api", public_host="demo.example.invalid", tls="acme"
        )
        notifier = MagicMock()
        AcmeEnsure(
            load_stack(self.tmp_path),
            config=AcmeConfig(email=None),
            notifier=notifier,
        ).run(["demo-api"])
        event = notifier.notify.call_args[0][0]
        assert event.kind == KIND_ACME_ERROR
        assert event.context["app"] == "demo-api"
