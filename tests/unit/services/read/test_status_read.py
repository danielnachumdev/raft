"""Shared StatusRead / DoctorRead contract tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.models import EDGE_GROUP
from raft.services.ops.doctor.models import CheckResult
from raft.services.ops.status.models import StatusSnapshot
from raft.services.read import DoctorRead, StatusRead

from ...base import RaftTestCase, make_stack
from ...services.ops.status.fixtures import StatusFixtures


class TestStatusRead(RaftTestCase):
    def test_snapshot_dict_matches_status_to_dict(self) -> None:
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(
                StatusFixtures.container("raft-gate", role="gate", group=EDGE_GROUP),
            ),
        )
        status = MagicMock()
        status.collect.return_value = snap
        reader = StatusRead(make_stack(self.tmp_path), status=status)
        assert reader.status is status
        assert reader.snapshot_dict() == snap.to_dict()
        status.collect.assert_called_once()

    def test_api_payload_shares_collector_and_adds_rows(self) -> None:
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(
                StatusFixtures.container("raft-gate", role="gate", group=EDGE_GROUP),
                StatusFixtures.container("site", role="app", app="site"),
            ),
        )
        status = MagicMock()
        status.collect.return_value = snap
        payload = StatusRead(make_stack(self.tmp_path), status=status).api_payload()
        assert payload["host"] == snap.to_dict()["host"]
        assert payload["containers"] == snap.to_dict()["containers"]
        assert payload["control_plane"][0]["name"] == "gate"
        assert payload["control_plane"][0]["external_urls"] == []
        assert payload["apps"][0]["name"] == "site"
        assert payload["apps"][0]["external_urls"] == []
        status.collect.assert_called_once()

    def test_service_detail_known_and_unknown(self) -> None:
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(
                StatusFixtures.container("raft-gate", role="gate", group=EDGE_GROUP),
            ),
        )
        status = MagicMock()
        status.collect.return_value = snap
        reader = StatusRead(make_stack(self.tmp_path), status=status)
        detail = reader.service_detail("raft-gate")
        assert detail is not None
        assert detail["container"]["service"] == "raft-gate"
        assert detail["presentation"]["name"] == "gate"
        assert detail["presentation"]["external_urls"] == []
        assert reader.service_detail("missing") is None
        assert status.collect.call_count == 2

    def test_api_payload_includes_app_external_urls(self) -> None:
        from ...base import make_app, write_applied_app

        write_applied_app(
            self.tmp_path, "site", public_host="site.test", www=False, tls="origin"
        )
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(
                StatusFixtures.container("site", role="app", app="site"),
            ),
        )
        status = MagicMock()
        status.collect.return_value = snap
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        payload = StatusRead(stack, status=status).api_payload()
        assert payload["apps"][0]["external_urls"] == ["https://site.test/"]


class TestDoctorRead(RaftTestCase):
    def test_from_results_and_shape(self) -> None:
        payload = DoctorRead.from_results(
            [
                CheckResult("raft-gate", "running", "ok", "up", ""),
                CheckResult("site", "upstream", "fail", "missing", "raft render"),
            ]
        )
        DoctorRead.assert_shape(payload)
        assert payload["results"][1]["fix"] == "raft render"
    def test_assert_shape_rejects_bad_payload(self) -> None:
        try:
            DoctorRead.assert_shape({})
        except AssertionError as exc:
            assert "results" in str(exc)
        try:
            DoctorRead.assert_shape({"results": [1]})
        except AssertionError as exc:
            assert "object" in str(exc)
        try:
            DoctorRead.assert_shape({"results": [{"service": "x"}]})
        except AssertionError as exc:
            assert "missing" in str(exc)
