#!/usr/bin/env python3
"""Label-driven semver for GitHub Releases (source of truth: release tags).

Used by ``.github/workflows/release.yml``. Prefer Release tags over
``pyproject.toml`` so CI does not bot-commit version files.

Bump labels (exact names, mutually exclusive with each other and ``noBump``):
``bumpMajor``, ``bumpMinor``, ``bumpPatch``, ``noBump``.

If none of those labels are present, exit non-zero (require explicit label).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterable, Optional, Sequence, Tuple

BUMP_LABELS = ("bumpMajor", "bumpMinor", "bumpPatch")
CONTROL_LABELS = BUMP_LABELS + ("noBump",)
_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class LabelError(ValueError):
    """Invalid or missing release label set."""


def parse_version(tag: str) -> Tuple[int, int, int]:
    """Parse ``vX.Y.Z`` or ``X.Y.Z`` into a triple."""
    cleaned = (tag or "").strip()
    if cleaned.lower().startswith("refs/tags/"):
        cleaned = cleaned[len("refs/tags/") :]
    match = _TAG_RE.match(cleaned)
    if not match:
        raise ValueError(f"unsupported version tag: {tag!r} (expected vX.Y.Z)")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_tag(major: int, minor: int, patch: int) -> str:
    return f"v{major}.{minor}.{patch}"


def resolve_action(labels: Iterable[str]) -> str:
    """Return ``major``|``minor``|``patch``|``none`` or raise ``LabelError``."""
    present = sorted({label for label in labels if label in CONTROL_LABELS})
    if not present:
        raise LabelError(
            "missing release label: add exactly one of "
            "bumpMajor, bumpMinor, bumpPatch, or noBump"
        )
    if len(present) > 1:
        raise LabelError(
            "multiple release labels on PR (fail closed): "
            + ", ".join(present)
            + " — keep exactly one"
        )
    chosen = present[0]
    if chosen == "noBump":
        return "none"
    return {
        "bumpMajor": "major",
        "bumpMinor": "minor",
        "bumpPatch": "patch",
    }[chosen]


def bump_version(
    current: Tuple[int, int, int], action: str
) -> Optional[Tuple[int, int, int]]:
    """Apply bump action; ``none`` returns ``None`` (skip release)."""
    if action == "none":
        return None
    major, minor, patch = current
    if action == "major":
        return major + 1, 0, 0
    if action == "minor":
        return major, minor + 1, 0
    if action == "patch":
        return major, minor, patch + 1
    raise ValueError(f"unknown bump action: {action!r}")


def next_tag(latest_tag: str, labels: Sequence[str]) -> Optional[str]:
    """Compute next ``vX.Y.Z`` from latest release tag + PR labels."""
    action = resolve_action(labels)
    base = parse_version(latest_tag) if latest_tag.strip() else (0, 0, 0)
    nxt = bump_version(base, action)
    if nxt is None:
        return None
    return format_tag(*nxt)


def _labels_from_args(raw_labels: Sequence[str], labels_json: str) -> list:
    if labels_json.strip():
        data = json.loads(labels_json)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return [str(item.get("name", "")) for item in data]
            return [str(item) for item in data]
        raise ValueError("--labels-json must be a JSON array")
    return list(raw_labels)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latest-tag",
        default="",
        help="Latest GitHub Release tag (empty ⇒ treat as 0.0.0)",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        dest="labels",
        help="PR label name (repeatable)",
    )
    parser.add_argument(
        "--labels-json",
        default="",
        help='JSON array of label names or GitHub label objects',
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        labels = _labels_from_args(args.labels, args.labels_json)
        action = resolve_action(labels)
        tag = next_tag(args.latest_tag, labels)
    except (LabelError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    # Machine-readable lines for GitHub Actions step outputs.
    print(f"action={action}")
    if tag is None:
        print("skip=true")
        print("tag=")
    else:
        print("skip=false")
        print(f"tag={tag}")
        print(f"version={tag.lstrip('v')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
