"""IP/CIDR access-control policy shared by gate settings and per-app ACL store."""

import ipaddress
from dataclasses import dataclass
from typing import Any, Mapping

from raft.core.core.errors.cta import OperatorError

ACL_MODES = frozenset({"off", "whitelist", "blacklist"})


@dataclass(frozen=True)
class AclEntry:
    """One durable allow/deny CIDR row."""

    id: str
    cidr: str
    comment: str = ""

    def to_public(self) -> dict[str, str]:
        return {"id": self.id, "cidr": self.cidr, "comment": self.comment}


@dataclass(frozen=True)
class AclPolicy:
    """Whitelist or blacklist of client CIDRs (``mode=off`` means inactive)."""

    mode: str = "off"
    entries: tuple[AclEntry, ...] = ()

    def is_active(self) -> bool:
        return self.mode in {"whitelist", "blacklist"} and bool(self.entries)

    def to_public(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "entries": [entry.to_public() for entry in self.entries],
        }

    @classmethod
    def from_mapping(cls, raw: Any, *, path: str) -> "AclPolicy":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{mode: whitelist|blacklist|off, entries: [...]}}",
                has_fix=False,
            )
        mode = cls._parse_mode(raw.get("mode"), path=path)
        entries = cls._parse_entries(raw.get("entries"), path=path)
        if mode in {"whitelist", "blacklist"} and not entries:
            raise OperatorError(
                f"{path}: mode={mode} requires at least one entry.\n"
                f"Fix: add a CIDR entry or set mode to off",
                has_fix=False,
            )
        return cls(mode=mode, entries=entries)

    @staticmethod
    def _parse_mode(raw: Any, *, path: str) -> str:
        mode = str(raw if raw is not None else "off").strip().lower()
        if mode not in ACL_MODES:
            raise OperatorError(
                f"{path}.mode must be one of off, whitelist, blacklist "
                f"(got {mode!r}).\n"
                f"Fix: set mode to whitelist or blacklist (or off)",
                has_fix=False,
            )
        return mode

    @classmethod
    def _parse_entries(cls, raw: Any, *, path: str) -> tuple[AclEntry, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path}.entries must be a list.\n"
                f"Fix: set entries: [{{id: office, cidr: 192.0.2.0/24}}]",
                has_fix=False,
            )
        entries = [
            cls._one_entry(item, f"{path}.entries[{index}]")
            for index, item in enumerate(raw)
        ]
        cls._assert_unique_ids(entries, path=path)
        return tuple(entries)

    @classmethod
    def _one_entry(cls, raw: Any, path: str) -> AclEntry:
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{id: office, cidr: 192.0.2.0/24, comment?: …}}",
                has_fix=False,
            )
        entry_id = str(raw.get("id") or "").strip()
        if not entry_id:
            raise OperatorError(
                f"{path}.id is required.\n"
                f"Fix: set a unique id (e.g. office)",
                has_fix=False,
            )
        cidr = AclCidr.validate(raw.get("cidr"), path=f"{path}.cidr")
        comment = str(raw.get("comment") or "").strip()
        return AclEntry(id=entry_id, cidr=cidr, comment=comment)

    @staticmethod
    def _assert_unique_ids(entries: list[AclEntry], *, path: str) -> None:
        seen: set[str] = set()
        for entry in entries:
            if entry.id in seen:
                raise OperatorError(
                    f"{path}.entries duplicate id {entry.id!r}.\n"
                    f"Fix: give each ACL entry a unique id",
                    has_fix=False,
                )
            seen.add(entry.id)


class AclCidr:
    """Validate operator CIDR / IP strings for nginx access rules."""

    @staticmethod
    def validate(raw: Any, *, path: str) -> str:
        text = str(raw or "").strip()
        if not text:
            raise OperatorError(
                f"{path} is required.\n"
                f"Fix: set a CIDR or IP (e.g. 192.0.2.0/24 or 192.0.2.10)",
                has_fix=False,
            )
        try:
            network = ipaddress.ip_network(text, strict=False)
        except ValueError as exc:
            raise OperatorError(
                f"{path} is not a valid IP or CIDR ({text!r}): {exc}.\n"
                f"Fix: use e.g. 192.0.2.0/24 or 192.0.2.10",
                has_fix=False,
            ) from exc
        return str(network)
