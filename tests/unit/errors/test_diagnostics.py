"""Unit tests for service log-relay / diagnostics helpers."""

from __future__ import annotations

from raft.errors import (
    append_diagnostics,
    compact_log_lines,
    compose_services_from_failure_text,
    format_service_log_block,
    join_diagnostic_blocks,
    prefer_errorish_lines,
    summarize_health_inspect,
)


class TestDiagnosticsHelpers:
    def test_compact_and_prefer_errorish(self) -> None:
        blob = "\n".join(
            [
                "info starting",
                "nginx: [emerg] host not found in upstream \"old-backend:8000\"",
                "info other",
            ]
        )
        assert "emerg" in prefer_errorish_lines(blob)
        assert "old-backend" in prefer_errorish_lines(blob)
        assert compact_log_lines("\n\na\n\nb\n", max_lines=1) == "b"
        assert compact_log_lines("   \n") == ""
        assert prefer_errorish_lines("") == ""

    def test_format_service_log_block(self) -> None:
        block = format_service_log_block(
            "frontend-dev",
            'nginx: [emerg] host not found in upstream "backend:8000"',
            health="running/unhealthy",
        )
        assert "--- frontend-dev (running/unhealthy) ---" in block
        assert "host not found" in block
        assert format_service_log_block("x", "", health="") == ""
        assert "--- x (absent) ---" == format_service_log_block("x", "", health="absent")

    def test_join_and_append(self) -> None:
        joined = join_diagnostic_blocks("a", "", "b")
        assert joined == "a\n\nb"
        assert append_diagnostics("timed out", "") == "timed out"
        assert "emerg" in append_diagnostics(
            "timed out waiting for: app_tmp",
            "--- raft-app_tmp ---\nnginx: [emerg] boom",
        )

    def test_compose_services_from_failure_text(self) -> None:
        text = (
            "dependency failed to start: "
            "container raft-limudpsanter-frontend-dev-1 is unhealthy"
        )
        found = compose_services_from_failure_text(
            text,
            known_services=("limudpsanter-frontend-dev", "limudpsanter-backend-dev"),
        )
        assert found[0] == "limudpsanter-frontend-dev"
        assert "limudpsanter-frontend-dev" in compose_services_from_failure_text(
            "service limudpsanter-frontend-dev failed",
            known_services=("limudpsanter-frontend-dev",),
        )
        # Non-project container name is kept as-is.
        assert compose_services_from_failure_text(
            "container weird_name is unhealthy"
        ) == ["weird_name"]

    def test_summarize_health_inspect(self) -> None:
        assert summarize_health_inspect("running", "healthy") == "running/healthy"
        assert summarize_health_inspect("running", "none") == "running"
        summary = summarize_health_inspect(
            "running",
            "unhealthy",
            last_output="wget: can't connect\n",
        )
        assert "running/unhealthy" in summary
        assert "healthcheck:" in summary
