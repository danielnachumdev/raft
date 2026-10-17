"""CLI argv dispatch for ``raft http_requests …``."""

from unittest.mock import patch

from raft.core.core.models.stack import Stack
from tests.unit.base import AppliedInventory
from tests.unit.services.cli.base import CliTestCase


class TestHttpRequestsCliArgv(CliTestCase):
    def test_show_argv(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path, "demo-api", public_host="demo-api.test"
        )
        self.stack = Stack.load_apps(self.tmp_path)
        with patch("raft.services.cli.commands.http_requests.OperatorSay.say"):
            assert (
                self.run_main(["http_requests", "show", "demo-api", "--json"]) == 0
            )
            assert self.run_main(["http_requests", "show", "demo-api"]) == 0
