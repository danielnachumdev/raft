"""HostOneshotFailures message and detail parsing branches."""

from raft.core.platform.adapters.docker.host_oneshot_failures import (
    HostOneshotFailures,
)


class TestHostOneshotFailures:
    def test_env_path_from_detail_edge_cases(self) -> None:
        failures = HostOneshotFailures()
        assert failures.env_path_from_detail("unrelated line\n") is None
        assert (
            failures.env_path_from_detail(
                "missing env file /tmp/x not found elsewhere"
            )
            is None
        )
        assert failures.env_path_from_detail("env file not found") is None
        assert failures.env_path_from_detail("env file  not found") is None
        assert (
            failures.env_path_from_detail(
                "env file /home/demo/.raft/services/demo-api/secrets/env "
                "not found"
            )
            == "/home/demo/.raft/services/demo-api/secrets/env"
        )

    def test_summary_unknown_and_image_noise(self) -> None:
        failures = HostOneshotFailures()
        assert failures.summary("   \n") == "unknown error"
        assert (
            failures.summary("Run `raft doctor` for a full check.\n")
            == "unknown error"
        )
        assert failures.looks_like_error("Image raft-demo Building") is False
        assert failures.looks_like_error("layer building now") is False

    def test_summary_drops_fix_tail_branches(self) -> None:
        failures = HostOneshotFailures()
        assert failures.summary("pull failed\nFix") == "pull failed"
        assert failures.summary("pull failed\nHint: retry") == "pull failed"
        assert failures.summary("pull failed\n1. raft doctor") == "pull failed"
        assert (
            failures.summary("pull failed\n--- demo (absent) ---")
            == "pull failed"
        )

    def test_fix_step_line_and_generic_message(self) -> None:
        failures = HostOneshotFailures()
        assert failures.is_fix_step_line("ab") is False
        assert failures.is_fix_step_line("nope. x") is False
        assert failures.is_fix_step_line("1. raft doctor") is True
        assert "host Docker one-shot failed" in failures.message(
            RuntimeError("something failed hard")
        )

    def test_env_file_message_falls_back_path(self) -> None:
        failures = HostOneshotFailures()
        msg = failures.known_message(
            "compose said env file missing and not found for demo"
        )
        assert msg is not None
        assert "~/.raft/services/<app>/secrets/env" in msg
