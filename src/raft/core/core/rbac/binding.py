"""One subject → role binding."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RbacBinding:
    """One subject → role binding."""

    subject: str
    role: str
