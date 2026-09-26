"""Unit tests for Fire argv peeling (repeatable --env)."""

from __future__ import annotations

from raft.cli.argv import ApplyEnvOverrides, RepeatableFlagPeeler

APPLY_ENV_ARGV = [
    "apply", "--file", "a.yaml", "--env", "A=1",
    "--env-file", "vars.env", "--env=B=2", "--no-deploy",
]


def test_peel_repeatable_env_keeps_env_file_and_other_flags() -> None:
    env_values, remaining = RepeatableFlagPeeler().peel(APPLY_ENV_ARGV, "--env")
    assert env_values == ["A=1", "B=2"]
    assert remaining == [
        "apply", "--file", "a.yaml", "--env-file", "vars.env", "--no-deploy",
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
