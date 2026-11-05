"""Print temporary GitOps override warnings after mutative CLI writes."""

from raft.core.core.gitops import GitopsDocKind, TemporaryOverrideWarn
from raft.core.core.ui import OperatorSay


class GitopsCliWarn:
    """CLI adapter for :class:`TemporaryOverrideWarn`."""

    @staticmethod
    def after_write(kind: GitopsDocKind) -> None:
        OperatorSay.say(TemporaryOverrideWarn.after_write(kind))

    @staticmethod
    def after_tips_dismiss(kind: GitopsDocKind) -> None:
        OperatorSay.say(TemporaryOverrideWarn.after_tips_dismiss(kind))
