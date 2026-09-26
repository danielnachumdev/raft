"""Controller stub process."""

from __future__ import annotations

import runpy
from unittest.mock import patch

import pytest

from raft.controller import main


class TestControllerStub:
    def test_main_idles_until_interrupted(self) -> None:
        with patch("raft.controller.time.sleep", side_effect=StopIteration):
            with pytest.raises(StopIteration):
                main()

    def test_module_entrypoint(self) -> None:
        with patch("raft.controller.time.sleep", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.controller", run_name="__main__")

    def test_main_module_import_does_not_run(self) -> None:
        import raft.controller.__main__ as controller_main

        assert controller_main.main is main
