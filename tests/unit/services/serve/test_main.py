"""``python -m raft.services.serve`` entry."""

import importlib
import runpy
from unittest.mock import MagicMock, patch

import pytest

from raft.services.serve import Serve
from raft.services.serve.entry import ServeMain, main

from tests.unit.base import RaftTestCase, StackMakers


class TestServeMain(RaftTestCase):
    def test_run_starts_serve(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        serve = MagicMock(spec=Serve)
        with patch("raft.services.serve.entry.load_stack", return_value=stack):
            with patch("raft.services.serve.entry.Serve", return_value=serve) as cls:
                ServeMain().run(["--port", "9001"])
        cls.assert_called_once_with(stack)
        serve.run.assert_called_once_with(port=9001)
        serve.stop.assert_not_called()

    def test_run_stop_flag(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path)
        serve = MagicMock(spec=Serve)
        with patch("raft.services.serve.entry.load_stack", return_value=stack):
            with patch("raft.services.serve.entry.Serve", return_value=serve):
                ServeMain().run(["--stop", "--port", "9002"])
        serve.stop.assert_called_once_with(port=9002)
        serve.run.assert_not_called()

    def test_module_entrypoint(self) -> None:
        with patch("raft.services.serve.entry.main", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.services.serve", run_name="__main__")

        main_mod = importlib.import_module("raft.services.serve.__main__")
        assert main_mod.main is main
