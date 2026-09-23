"""Unit tests for Fire argv peeling (repeatable --env)."""

from __future__ import annotations

from raft.cli.argv import (
    get_apply_env_overrides,
    peel_repeatable_flag,
    reset_apply_env_overrides,
    set_apply_env_overrides,
)


def test_peel_repeatable_env_forms() -> None:
    values, rest = peel_repeatable_flag(
        [
            "apply",
            "--file",
            "a.yaml",
            "--env",
            "A=1",
            "--env-file",
            "vars.env",
            "--env=B=2",
            "--no-deploy",
        ],
        "--env",
    )
    assert values == ["A=1", "B=2"]
    assert rest == [
        "apply",
        "--file",
        "a.yaml",
        "--env-file",
        "vars.env",
        "--no-deploy",
    ]


def test_peel_dangling_flag_left_in_remaining() -> None:
    values, rest = peel_repeatable_flag(["apply", "--env"], "--env")
    assert values == []
    assert rest == ["apply", "--env"]
    # Flag without leading dashes is normalized.
    values2, rest2 = peel_repeatable_flag(["--env=Z=9"], "env")
    assert values2 == ["Z=9"]
    assert rest2 == []


def test_apply_env_contextvar_roundtrip() -> None:
    assert get_apply_env_overrides() == ()
    token = set_apply_env_overrides(["X=1", "Y=2"])
    try:
        assert get_apply_env_overrides() == ("X=1", "Y=2")
    finally:
        reset_apply_env_overrides(token)
    assert get_apply_env_overrides() == ()
