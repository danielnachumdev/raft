"""Git auth/network/generic error classifiers and raise_for_git_failure."""

from __future__ import annotations

import subprocess

import pytest

from raft.errors import (
    OperatorError,
    git_auth_failure_message,
    git_generic_failure_message,
    git_network_failure_message,
    looks_like_git_auth_failure,
    looks_like_git_network_failure,
    raise_for_git_failure,
)

from ...cta_asserts import assert_cta, assert_operator


class TestGitErrors:
    def test_classifiers_and_messages(self) -> None:
        self._assert_auth_messages()
        self._assert_network_messages()
        self._assert_generic_messages()

    def _assert_auth_messages(self) -> None:
        auth = subprocess.CalledProcessError(
            1, ["git"], stderr="Permission denied (publickey)"
        )
        assert looks_like_git_auth_failure(auth)
        assert_cta(
            git_auth_failure_message("git@h:o/r.git", app="web", detail="nope\n"),
            contains=("auth setup web", "auth test web"),
            fix_label="Fix (as the raft user):",
            tag="git",
        )
        assert_cta(
            git_auth_failure_message("r", detail="  "),
            contains=("auth setup",),
            fix_label="Fix (as the raft user):",
        )
        assert_cta(
            git_auth_failure_message("r", detail="\n\n"),
            contains=("auth setup",),
            fix_label="Fix (as the raft user):",
        )

    def _assert_network_messages(self) -> None:
        net = RuntimeError("Could not resolve host: github.com")
        assert looks_like_git_network_failure(net)
        assert_cta(
            git_network_failure_message("r", detail="dns\nfail"),
            contains=("auth test",),
            tag="git",
        )
        assert_cta(git_network_failure_message("r", detail=""), contains=("auth test",))
        assert_cta(
            git_network_failure_message("r", detail="\n  \n"), contains=("auth test",)
        )

    def _assert_generic_messages(self) -> None:
        assert_cta(
            git_generic_failure_message("r", app="web", detail="x\n"),
            contains=("auth test web", "raft doctor"),
            tag="git",
        )
        assert_cta(
            git_generic_failure_message("r", detail="  "),
            contains=("auth test", "raft doctor"),
        )

    def test_raise_for_git_failure(self) -> None:
        with pytest.raises(OperatorError) as caught:
            raise_for_git_failure(
                subprocess.CalledProcessError(
                    1, ["git"], stderr="Could not read from remote repository"
                ),
                "git@h:o/r.git",
                app="web",
            )
        assert_operator(
            caught.value,
            contains=("auth setup web",),
            fix_label="Fix (as the raft user):",
        )
        with pytest.raises(OperatorError) as caught:
            raise_for_git_failure(RuntimeError("connection timed out"), "r")
        assert_operator(caught.value, contains=("auth test",))
        raise_for_git_failure(RuntimeError("weird"), "r")
        with pytest.raises(OperatorError) as caught:
            raise_for_git_failure(RuntimeError("weird"), "r", always=True)
        assert_operator(caught.value, contains=("auth test", "raft doctor"))
