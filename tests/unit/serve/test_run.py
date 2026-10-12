"""``Serve.run`` binds localhost and prints tunnel CTAs."""

from unittest.mock import patch

from raft.serve.service import DEFAULT_SERVE_PORT, Serve

from tests.unit.base import RaftTestCase, make_stack


class TestServeRun(RaftTestCase):
    def test_run_prints_instructions_and_starts_uvicorn(self, capsys) -> None:
        with patch("raft.serve.service.uvicorn.run") as run:
            Serve(make_stack(self.tmp_path)).run(port=DEFAULT_SERVE_PORT)
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8787/" in out
        assert "ssh -L 8787:127.0.0.1:8787" in out
        run.assert_called_once()
        args, kwargs = run.call_args
        assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 8787
        assert args[0] is not None
