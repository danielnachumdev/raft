"""Unit tests for Fire argv peeling (repeatable --env) and logs normalization."""

from __future__ import annotations

from raft.cli.commands.argv import ApplyEnvOverrides, RepeatableFlagPeeler
from raft.cli.commands.logs_argv import LogsArgvNormalizer

APPLY_ENV_ARGV = [
    "apply",
    "--file",
    "a.yaml",
    "--env",
    "A=1",
    "--env-file",
    "vars.env",
    "--env=B=2",
    "--no-deploy",
]


def test_peel_repeatable_env_keeps_env_file_and_other_flags() -> None:
    env_values, remaining = RepeatableFlagPeeler().peel(APPLY_ENV_ARGV, "--env")
    assert env_values == ["A=1", "B=2"]
    assert remaining == [
        "apply",
        "--file",
        "a.yaml",
        "--env-file",
        "vars.env",
        "--no-deploy",
    ]


def test_peel_dangling_env_flag_left_in_remaining() -> None:
    env_values, remaining = RepeatableFlagPeeler().peel(["apply", "--env"], "--env")
    assert env_values == []
    assert remaining == ["apply", "--env"]


def test_peel_normalizes_flag_name_without_leading_dashes() -> None:
    env_values, remaining = RepeatableFlagPeeler().peel(["--env=Z=9"], "env")
    assert env_values == ["Z=9"]
    assert remaining == []


def test_apply_env_contextvar_roundtrip() -> None:
    before = ApplyEnvOverrides.get()
    token = ApplyEnvOverrides.set(["X=1", "Y=2"])
    try:
        during = ApplyEnvOverrides.get()
    finally:
        ApplyEnvOverrides.reset(token)
    assert before == () and during == ("X=1", "Y=2")
    assert ApplyEnvOverrides.get() == ()


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
