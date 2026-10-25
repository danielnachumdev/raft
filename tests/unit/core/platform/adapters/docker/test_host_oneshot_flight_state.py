"""HostOneshotFlightState JSON persistence."""

from raft.core.platform.adapters.docker.host_oneshot_flight_state import (
    HostOneshotFlightState,
)

from tests.unit.base import RaftTestCase


class TestHostOneshotFlightState(RaftTestCase):
    def test_round_trip_and_clear(self) -> None:
        state = HostOneshotFlightState(self.tmp_path, "redeploy-dashboard")
        assert state.read_job_id() is None
        state.write_job_id("cid-abc")
        assert state.read_job_id() == "cid-abc"
        state.clear()
        assert state.read_job_id() is None

    def test_bad_json_returns_none(self) -> None:
        state = HostOneshotFlightState(self.tmp_path, "x")
        state.path.parent.mkdir(parents=True, exist_ok=True)
        state.path.write_text("{not-json", encoding="utf-8")
        assert state.read_job_id() is None

    def test_non_object_or_blank_job(self) -> None:
        state = HostOneshotFlightState(self.tmp_path, "y")
        state.path.parent.mkdir(parents=True, exist_ok=True)
        state.path.write_text("[1]\n", encoding="utf-8")
        assert state.read_job_id() is None
        state.path.write_text('{"job_id": "  "}\n', encoding="utf-8")
        assert state.read_job_id() is None
        state.path.write_text('{"job_id": 1}\n', encoding="utf-8")
        assert state.read_job_id() is None

    def test_clear_oserror_is_swallowed(self, monkeypatch) -> None:
        state = HostOneshotFlightState(self.tmp_path, "z")
        state.write_job_id("cid")

        def _boom(*_a, **_k):
            raise OSError("denied")

        monkeypatch.setattr(type(state.path), "unlink", _boom)
        state.clear()
