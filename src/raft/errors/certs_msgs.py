"""Origin cert text classifiers and formatters (no Stack imports)."""

from __future__ import annotations

from typing import Any, Sequence


def looks_like_missing_origin_cert(text: str) -> bool:
    lower = text.lower()
    if "cannot load certificate" in lower and (
        "origin.pem" in lower or "/certs/" in lower
    ):
        return True
    if "bio_new_file" in lower and "origin." in lower:
        return True
    return False


def format_missing_origin_certs(
    missing: Sequence[Any],
    *,
    include_doctor_footer: bool = False,
) -> str:
    """Format items that expose ``app_name``, ``detail``, and ``fix``."""
    lines: list[str] = [
        "cannot deploy/reload gate: Cloudflare Origin certs missing:",
    ]
    for item in missing:
        lines.append(f"  {item.app_name}: {item.detail}")
        lines.append(f"    fix: {item.fix}")
    if include_doctor_footer:
        lines.append("Run `raft doctor` for a full check.")
    return "\n".join(lines)


def missing_origin_certs_fallback(*, detail: str = "") -> str:
    text = (
        "gate nginx could not load Origin TLS certificates "
        "(missing files under ~/.raft/certs/<app>/)."
    )
    if detail.strip():
        return f"{text}\n{detail.strip()}"
    return text
