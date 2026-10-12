"""Git auth/network/generic error classifiers and raise_for_git_failure."""

from __future__ import annotations

import subprocess

import pytest

from raft.core.core.errors.checked import CheckedCommands
from raft.core.core.errors.cta import CtaFormatter, OperatorError
from raft.core.core.errors.git_msgs import GitMessages

from tests.unit.cta_asserts import CtaAsserts


class TestGitErrors:
    def test_classifiers_and_messages(self) -> None:
        self._assert_auth_messages()
        self._assert_network_messages()
        self._assert_generic_messages()

    def _assert_auth_messages(self) -> None:
        auth = subprocess.CalledProcessError(1, ["git"], stderr="Permission denied (publickey)")
        assert GitMessages.looks_like_git_auth_failure(auth)
        CtaAsserts.cta(
            GitMessages.git_auth_failure_message("git@h:o/r.git", app="web", detail="nope\n"),
            contains=("auth setup web", "auth test web"),
            fix_label="Fix (as the raft user):",
            tag="git",
        )
        CtaAsserts.cta(
            GitMessages.git_auth_failure_message("r", detail="  "),
            contains=("auth setup",),
            fix_label="Fix (as the raft user):",
        )
        CtaAsserts.cta(
            GitMessages.git_auth_failure_message("r", detail="\n\n"),
            contains=("auth setup",),
            fix_label="Fix (as the raft user):",
        )

    def _assert_network_messages(self) -> None:
        net = RuntimeError("Could not resolve host: github.com")
        assert GitMessages.looks_like_git_network_failure(net)
        CtaAsserts.cta(
            GitMessages.git_network_failure_message("r", detail="dns\nfail"),
            contains=("auth test",),
            tag="git",
        )
        CtaAsserts.cta(GitMessages.git_network_failure_message("r", detail=""), contains=("auth test",))
        CtaAsserts.cta(GitMessages.git_network_failure_message("r", detail="\n  \n"), contains=("auth test",))

    def _assert_generic_messages(self) -> None:
        CtaAsserts.cta(
            GitMessages.git_generic_failure_message("r", app="web", detail="x\n"),
            contains=("auth test web", "raft doctor"),
            tag="git",
        )
        CtaAsserts.cta(
            GitMessages.git_generic_failure_message("r", detail="  "),
            contains=("auth test", "raft doctor"),
        )

    def test_raise_for_git_failure(self) -> None:
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_git_failure(
                subprocess.CalledProcessError(
                    1, ["git"], stderr="Could not read from remote repository"
                ),
                "git@h:o/r.git",
                app="web",
            )
        CtaAsserts.operator(
            caught.value,
            contains=("auth setup web",),
            fix_label="Fix (as the raft user):",
        )
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_git_failure(RuntimeError("connection timed out"), "r")
        CtaAsserts.operator(caught.value, contains=("auth test",))
        CheckedCommands.raise_for_git_failure(RuntimeError("weird"), "r")
        with pytest.raises(OperatorError) as caught:
            CheckedCommands.raise_for_git_failure(RuntimeError("weird"), "r", always=True)
        CtaAsserts.operator(caught.value, contains=("auth test", "raft doctor"))
