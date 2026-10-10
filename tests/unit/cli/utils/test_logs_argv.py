"""Unit tests for logs argv normalization."""

from __future__ import annotations

from raft.cli.utils.logs_argv import LogsArgvNormalizer


def test_logs_normalizer_moves_flags_after_services() -> None:
    assert LogsArgvNormalizer().normalize(
        ["logs", "-f", "--tail", "20", "gate", "app"]
    ) == ["logs", "gate", "app", "--follow", "--tail", "20"]


def test_logs_normalizer_leaves_non_logs_argv() -> None:
    assert LogsArgvNormalizer().normalize(["status", "--live"]) == ["status", "--live"]


def test_logs_normalizer_accepts_equals_forms() -> None:
    assert LogsArgvNormalizer().normalize(
        ["logs", "--follow=true", "--tail=5", "router"]
    ) == ["logs", "router", "--follow", "--tail", "5"]


def test_logs_normalizer_keeps_unknown_and_dangling_tail() -> None:
    assert LogsArgvNormalizer().normalize(["logs", "app", "--bogus"]) == [
        "logs",
        "app",
        "--bogus",
    ]
    assert LogsArgvNormalizer().normalize(["logs", "--tail"]) == ["logs", "--tail"]


def test_logs_normalizer_empty_argv() -> None:
    assert LogsArgvNormalizer().normalize([]) == []
