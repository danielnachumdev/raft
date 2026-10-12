"""Unit tests for logs argv normalization."""

from raft.services.cli.utils.logs_argv import LogsArgvNormalizer


class TestLogsArgvNormalizer:
    def test_moves_flags_after_services(self) -> None:
        assert LogsArgvNormalizer().normalize(
            ["logs", "-f", "--tail", "20", "gate", "app"]
        ) == ["logs", "gate", "app", "--follow", "--tail", "20"]

    def test_leaves_non_logs_argv(self) -> None:
        assert LogsArgvNormalizer().normalize(["status", "--live"]) == [
            "status",
            "--live",
        ]

    def test_accepts_equals_forms(self) -> None:
        assert LogsArgvNormalizer().normalize(
            ["logs", "--follow=true", "--tail=5", "router"]
        ) == ["logs", "router", "--follow", "--tail", "5"]

    def test_keeps_unknown_and_dangling_tail(self) -> None:
        assert LogsArgvNormalizer().normalize(["logs", "app", "--bogus"]) == [
            "logs",
            "app",
            "--bogus",
        ]
        assert LogsArgvNormalizer().normalize(["logs", "--tail"]) == [
            "logs",
            "--tail",
        ]

    def test_empty_argv(self) -> None:
        assert LogsArgvNormalizer().normalize([]) == []
