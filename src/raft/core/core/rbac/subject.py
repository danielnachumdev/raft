"""Normalize RBAC binding subjects for compare."""


class RbacSubject:
    """Subject string helpers (oauth email / password username)."""

    @staticmethod
    def normalize(raw: str) -> str:
        return str(raw or "").strip().lower()
