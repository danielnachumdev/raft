"""HostOneshotFlight coalesce + fresh start."""

from unittest.mock import MagicMock

from raft.core.platform.adapters.docker import HostOneshotFlight
from raft.core.platform.adapters.docker.host_oneshot_flight_state import (
    HostOneshotFlightState,
)
from raft.core.platform.locking import FifoLock, StackLock

from tests.unit.base import RaftTestCase


class TestHostOneshotFlight(RaftTestCase):
    def test_start_fresh_records_job(self) -> None:
        oneshot = MagicMock()
        oneshot.start.return_value = "cid-fresh"
        alive = MagicMock()
        alive.running.return_value = False
        flight = HostOneshotFlight(
            self.tmp_path,
            HostOneshotFlight.KIND_DASHBOARD_REDEPLOY,
            oneshot=oneshot,
            alive=alive,
        )
        started = flight.start(["raft", "redeploy", "dashboard"])
        assert started.job_id == "cid-fresh"
        assert started.coalesced is False
        oneshot.start.assert_called_once()
        state = HostOneshotFlightState(
            self.tmp_path, HostOneshotFlight.KIND_DASHBOARD_REDEPLOY
        )
        assert state.read_job_id() == "cid-fresh"

    def test_second_start_coalesces_while_alive(self) -> None:
        oneshot = MagicMock()
        oneshot.start.return_value = "cid-1"
        alive = MagicMock()
        alive.running.return_value = True
        flight = HostOneshotFlight(
            self.tmp_path,
            "redeploy-dashboard",
            oneshot=oneshot,
            alive=alive,
        )
        first = flight.start(["raft", "redeploy", "dashboard"])
        second = flight.start(["raft", "redeploy", "dashboard"])
        assert first.job_id == "cid-1"
        assert second.job_id == "cid-1"
        assert second.coalesced is True
        assert oneshot.start.call_count == 1
        alive.running.assert_called_once_with("cid-1")

    def test_dead_job_clears_and_starts_new(self) -> None:
        state = HostOneshotFlightState(self.tmp_path, "redeploy-dashboard")
        state.write_job_id("cid-dead")
        oneshot = MagicMock()
        oneshot.start.return_value = "cid-new"
        alive = MagicMock()
        alive.running.return_value = False
        flight = HostOneshotFlight(
            self.tmp_path,
            "redeploy-dashboard",
            oneshot=oneshot,
            alive=alive,
            state=state,
        )
        started = flight.start(["raft", "x"])
        assert started.job_id == "cid-new"
        assert started.coalesced is False
        assert state.read_job_id() == "cid-new"

    def test_flight_lock_released_before_stack_work(self) -> None:
        """Parent must not hold host-job FIFO across stack.lock (oneshot child)."""
        oneshot = MagicMock()
        oneshot.start.return_value = "cid-ok"
        alive = MagicMock()
        alive.running.return_value = False
        flight = HostOneshotFlight(
            self.tmp_path,
            "redeploy-dashboard",
            oneshot=oneshot,
            alive=alive,
        )
        flight.start(["raft", "redeploy", "dashboard"])
        with StackLock(self.tmp_path, timeout=1):
            with FifoLock(self.tmp_path, "host-job-redeploy-dashboard", timeout=1):
                pass
