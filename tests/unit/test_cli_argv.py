"""Unit tests for Fire argv peeling (repeatable --env)."""

from __future__ import annotations

from raft.cli.argv import (
    get_apply_env_overrides,
    peel_repeatable_flag,
    reset_apply_env_overrides,
    set_apply_env_overrides,
)


def test_peel_repeatable_env_keeps_env_file_and_other_flags() -> None:
    argv = [
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

    env_values, remaining = peel_repeatable_flag(argv, "--env")

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
    argv = ["apply", "--env"]

    env_values, remaining = peel_repeatable_flag(argv, "--env")

    assert env_values == []
    assert remaining == ["apply", "--env"]


def test_peel_normalizes_flag_name_without_leading_dashes() -> None:
    argv = ["--env=Z=9"]

    env_values, remaining = peel_repeatable_flag(argv, "env")

    assert env_values == ["Z=9"]
    assert remaining == []


def test_apply_env_contextvar_roundtrip() -> None:
    before = get_apply_env_overrides()
    token = set_apply_env_overrides(["X=1", "Y=2"])
    try:
        during = get_apply_env_overrides()
    finally:
        reset_apply_env_overrides(token)
    after = get_apply_env_overrides()

    assert before == ()
    assert during == ("X=1", "Y=2")
    assert after == ()
