"""Manifest parse / rewrite / fingerprint helpers for deploy jobs."""

import base64
import hashlib
from pathlib import Path
from typing import Optional

import yaml

from raft.core.core.errors.cta import OperatorError


class GithubDeployManifest:
    """YAML + pubkey helpers used while driving a GitHub deploy job."""

    @staticmethod
    def parse_yaml(text: str, full_name: str) -> dict:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid App manifest YAML in {full_name}: {exc}\n"
                f"Fix: repair .raft/app.yaml",
                has_fix=False,
            ) from exc
        if not isinstance(data, dict):
            raise OperatorError(
                f"app manifest must be a mapping in {full_name}\n"
                f"Fix: repair .raft/app.yaml",
                has_fix=False,
            )
        return data

    @staticmethod
    def manifest_name(data: dict) -> str:
        meta = data.get("metadata")
        if not isinstance(meta, dict) or not str(meta.get("name", "")).strip():
            raise OperatorError(
                "manifest metadata.name is required\n"
                "Fix: set metadata.name in .raft/app.yaml",
                has_fix=False,
            )
        return str(meta["name"]).strip()

    @staticmethod
    def rewrite_local(path: Path, data: dict, app_name: str) -> None:
        spec = data.setdefault("spec", {})
        if not isinstance(spec, dict):
            raise OperatorError("manifest spec must be a mapping", has_fix=False)
        spec["source"] = "local"
        spec["path"] = f"services/{app_name}/checkout"
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @staticmethod
    def registry_or(data: dict, path: Path) -> dict:
        if path.is_file():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or data
        return data

    @staticmethod
    def title_from_pubkey(pubkey: str) -> Optional[str]:
        parts = pubkey.split()
        if len(parts) >= 3:
            return " ".join(parts[2:]).strip() or None
        return None

    @staticmethod
    def fingerprint(pubkey: Optional[str]) -> str:
        if not pubkey:
            return ""
        parts = pubkey.split()
        blob = parts[1] if len(parts) >= 2 else pubkey
        try:
            raw = hashlib.sha256(base64.b64decode(blob + "==")).digest()
        except Exception:
            return "SHA256:(unparsed)"
        return "SHA256:" + base64.b64encode(raw).decode("ascii").rstrip("=")
