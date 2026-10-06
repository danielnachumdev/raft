"""Wake diagnostic id is logged on request and timeout."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.controller.scale import Scaler
from raft.errors.cta import OperatorError
from raft.models.scaling_spec import ScalingSpec

from .base import ControllerTestCase


class TestScaleWakeDiagId(ControllerTestCase):
    def test_request_and_timeout_logs_share_id(self, tmp_path: Path, caplog) -> None:
        scaler = Scaler(self.applied_home(tmp_path, extra=self.scaling_extra()), MagicMock())
        scaler.store.mark_scaled_to_zero(self.APP)
        with patch.object(scaler, "_start_wake_thread"):
            with caplog.at_level("INFO"):
                scaler.request_wake(self.APP)
        wake_id = scaler.store.load(self.APP).wake_id
        assert wake_id
        assert f"scale wake request app={self.APP} id={wake_id}" in caplog.text
        state = scaler.store.load(self.APP)
        state.wake_requested_at = 0.0
        scaler.store.save(self.APP, state)
        with caplog.at_level("WARNING"):
            scaler.tick(now=40.0)
        assert f"scale wake timeout app={self.APP} id={wake_id}" in caplog.text

    def test_do_wake_logs_id(self, tmp_path: Path, caplog) -> None:
        docker = MagicMock()
        scaler = Scaler(self.applied_home(tmp_path, extra=self.scaling_extra()), docker)
        scaler.store.mark_scaled_to_zero(self.APP)
        scaler.store.request_wake(self.APP, now=0.0)
        wake_id = scaler.store.load(self.APP).wake_id
        docker.service_runtime.return_value = ("exited", "none")
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        with self.with_scale_locks(), caplog.at_level("INFO"):
            scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0)
        assert f"scale wake app={self.APP} id={wake_id}" in caplog.text
        assert f"scale wake failed app={self.APP} id={wake_id}" in caplog.text
