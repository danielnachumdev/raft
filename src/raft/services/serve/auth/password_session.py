"""Password verification for dashboard password auth."""

from pathlib import Path
from typing import Dict, Mapping, Optional

from raft.core.lifecycle.dashboard.password import DashboardPassword


class PasswordSessionAuth:
    """PBKDF2 verify against configured username → hash map."""

    def __init__(
        self,
        data_home: Path,
        *,
        users: Mapping[str, str],
    ) -> None:
        self._users = {str(k).strip().lower(): v for k, v in users.items() if k}
        self._password = DashboardPassword()
        self._data_home = data_home

    @classmethod
    def from_hashes(
        cls,
        data_home: Path,
        *,
        password_hash: Optional[str] = None,
        users: Optional[Mapping[str, str]] = None,
    ) -> "PasswordSessionAuth":
        merged: Dict[str, str] = {}
        if users:
            merged.update(users)
        if password_hash and "admin" not in merged:
            merged["admin"] = password_hash
        return cls(data_home, users=merged)

    def verify(self, password: str, *, username: Optional[str] = None) -> Optional[str]:
        """Return normalized username when the password matches."""
        user = (username or "admin").strip().lower()
        encoded = self._users.get(user)
        if not encoded or not self._password.verify(password, encoded):
            return None
        return user
