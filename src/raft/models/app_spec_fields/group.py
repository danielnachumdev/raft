"""Parse ``spec.group`` and ``spec.extraHosts``."""

from pathlib import Path
from typing import Any, Optional

from .known_keys import GROUP_NAME


class AppGroupFields:
    """Parse App group membership and Host aliases."""

    @staticmethod
    def parse_group(spec: dict[str, Any], path: Path) -> Optional[str]:
        if "groups" in spec and spec.get("groups") is not None:
            raise ValueError(
                f"{path}: use spec.group (a single string), not spec.groups"
            )
        raw = spec.get("group")
        if raw is None:
            return None
        if isinstance(raw, list):
            raise ValueError(
                f"{path}: spec.group must be a string (at most one group), not a list"
            )
        if not isinstance(raw, str):
            raise ValueError(f"{path}: spec.group must be a string")
        return AppGroupFields._validated_name(raw.strip(), path)

    @staticmethod
    def _validated_name(text: str, path: Path) -> Optional[str]:
        if not text:
            return None
        if not GROUP_NAME.match(text):
            raise ValueError(
                f"{path}: spec.group {text!r} must match {GROUP_NAME.pattern}"
            )
        return text

    @staticmethod
    def extra_hosts(spec: dict[str, Any], path: Path) -> tuple[str, ...]:
        extra_raw = spec.get("extraHosts", spec.get("extra_hosts"))
        if extra_raw is None:
            return ()
        if isinstance(extra_raw, str):
            return (extra_raw.strip(),) if extra_raw.strip() else ()
        if isinstance(extra_raw, list):
            return tuple(str(x).strip() for x in extra_raw if str(x).strip())
        raise ValueError(f"{path}: spec.extraHosts must be a string or array")
