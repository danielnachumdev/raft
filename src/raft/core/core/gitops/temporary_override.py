"""Temporary host-override copy for GitOps flat docs (#310 / #318)."""

from .doc_kind import GitopsDocKind


class TemporaryOverrideWarn:
    """Operator-facing warnings when live host GitOps files are mutated."""

    @staticmethod
    def host_path(kind: GitopsDocKind) -> str:
        return f"host/{kind.value}.yaml"

    @classmethod
    def write_message(cls, kind: GitopsDocKind) -> str:
        path = cls.host_path(kind)
        return (
            "Temporary host override — next GitOps sync "
            f"(vpsctl Sync host config) will replace {path}."
        )

    @classmethod
    def after_write(cls, kind: GitopsDocKind) -> str:
        return f"warning: {cls.write_message(kind)}"

    @classmethod
    def tips_dismiss_message(cls, kind: GitopsDocKind) -> str:
        path = cls.host_path(kind)
        return (
            "Tip dismiss is host-local and temporary. "
            f"For a lasting hide, set disable_tips: true on {path} "
            "in the GitOps repo, then Sync."
        )

    @classmethod
    def after_tips_dismiss(cls, kind: GitopsDocKind) -> str:
        return f"warning: {cls.tips_dismiss_message(kind)}"
