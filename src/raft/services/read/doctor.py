"""Structured doctor results for a future dashboard health view (#34)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from ..ops.doctor.models import CheckResult


class DoctorRead:
    """Thin JSON export over ``Doctor.run()`` results (not a second checker).

    Intended HTTP shape (not wired to serve yet)::

        {
          "results": [
            {
              "service": "raft-gate",
              "check": "running",
              "status": "ok" | "warn" | "fail",
              "detail": "...",
              "fix": "..."
            }
          ]
        }

    Grouping for display stays in ``GroupReportWriter`` for the CLI; the FE can
    group by ``service`` / raft group conventions later without re-running checks.
    """

    intended_payload_shape = (
        "GET (future) /api/doctor → { results: CheckResult[] } "
        "where each result has service, check, status, detail, fix"
    )

    @staticmethod
    def from_results(results: Iterable[CheckResult]) -> Dict[str, Any]:
        return {"results": [DoctorRead._one(r) for r in results]}

    @staticmethod
    def _one(result: CheckResult) -> Dict[str, str]:
        return {
            "service": result.service,
            "check": result.check,
            "status": result.status,
            "detail": result.detail,
            "fix": result.fix,
        }

    @staticmethod
    def assert_shape(payload: Mapping[str, Any]) -> None:
        """Raise AssertionError if payload is not the intended doctor shape."""
        results = payload.get("results")
        if not isinstance(results, list):
            raise AssertionError("doctor payload missing results list")
        for row in results:
            DoctorRead._assert_row(row)

    @staticmethod
    def _assert_row(row: Any) -> None:
        if not isinstance(row, dict):
            raise AssertionError("doctor result must be an object")
        for key in ("service", "check", "status", "detail", "fix"):
            if key not in row:
                raise AssertionError(f"doctor result missing {key!r}")
