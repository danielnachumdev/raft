"""Origin / ACME cert text classifiers and formatters (no Stack imports)."""

from __future__ import annotations

from typing import Any, Sequence


def looks_like_missing_acme_cert(text: str) -> bool:
    lower = text.lower()
    if "acme.pem" in lower or "acme.key" in lower:
        return True
    if "bio_new_file" in lower and "acme." in lower:
        return True
    return False


def looks_like_missing_origin_cert(text: str) -> bool:
    if looks_like_missing_acme_cert(text):
        return False
    lower = text.lower()
    if "cannot load certificate" in lower and ("origin.pem" in lower or "/certs/" in lower):
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


def format_missing_acme_certs(
    missing: Sequence[Any],
    *,
    include_doctor_footer: bool = False,
) -> str:
    """Format ACME missing-material items (DNS/email CTAs — not Origin PEMs)."""
    lines: list[str] = [
        "cannot deploy/reload gate: ACME TLS certificates missing:",
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


def missing_acme_certs_fallback(*, detail: str = "") -> str:
    text = (
        "gate nginx could not load ACME TLS certificates "
        "(missing files under ~/.raft/certs/<app>/acme.pem). "
        "Fix: point DNS A/AAAA at this host; keep edge.http (:80) and "
        "edge.https (:443) published; set acme.email; re-apply "
        "(do not paste Origin PEMs for tls: acme)."
    )
    if detail.strip():
        return f"{text}\n{detail.strip()}"
    return text
