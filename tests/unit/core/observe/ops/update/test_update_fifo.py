"""SelfUpdate takes FifoLock(update) for FCFS exclusive install."""

from unittest.mock import MagicMock, patch

from raft.core.observe.ops import update as update_mod
from raft.core.observe.ops.update import HostApplyGate, SelfUpdate
from raft.core.core.ui.progress import TerminalProgress

from tests.unit.domain_case import DomainTestCase


class _CaptureFifo:
    held: list[str] = []

    def __init__(self, root, kind, *, timeout=None) -> None:
        del root, timeout
        type(self).held.append(kind)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class TestSelfUpdateFifo(DomainTestCase):
    def setup_method(self) -> None:
        TerminalProgress._active = None
        _CaptureFifo.held = []

    def teardown_method(self) -> None:
        TerminalProgress._active = None

    def test_run_holds_fifo_update_lock(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        monkeypatch.setattr(
            "raft.core.observe.ops.update.service.FifoLock", _CaptureFifo
        )
        upd = self._upd()
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run()
        assert _CaptureFifo.held == ["update"]

    def _upd(self) -> SelfUpdate:
        gate = MagicMock(spec=HostApplyGate)
        gate.ensure = MagicMock()
        gate.uses_host_docker.return_value = False
        upd = SelfUpdate(self.stack, host_gate=gate)
        upd.sh = MagicMock()
        return upd
