"""Readable service diagnostics for OperatorError / doctor output.

Declarative helpers: format log tails and health lines so operators see the
concrete nginx/oauth/exit reason without SSHing for ``docker compose logs``.
"""

from __future__ import annotations

import re
from typing import Sequence

# Compose: "dependency failed to start: container raft-foo-1 is unhealthy"
_CONTAINER_FAIL_RE = re.compile(
    r"container\s+(?P<name>[\w.-]+)\s+is\s+(?P<state>unhealthy|restarting|dead)",
    re.IGNORECASE,
)
# Project-prefixed container → compose service: raft-<service>-N
_PROJECT_CONTAINER_RE = re.compile(
    r"^raft-(?P<service>.+)-\d+$",
    re.IGNORECASE,
)


def compact_log_lines(text: str, *, max_lines: int = 20) -> str:
    """Keep the last non-empty lines of a log blob (short for CTAs)."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def format_service_log_block(
    label: str,
    logs: str,
    *,
    health: str = "",
    max_lines: int = 20,
) -> str:
    """Render ``--- label (health) ---`` plus a compact log tail."""
    body = compact_log_lines(logs, max_lines=max_lines)
    status = health.strip()
    header = f"--- {label}"
    if status:
        header = f"{header} ({status})"
    header = f"{header} ---"
    if not body:
        return header if status else ""
    return f"{header}\n{body}"


def join_diagnostic_blocks(*blocks: str) -> str:
    """Join non-empty diagnostic blocks with a blank line."""
    parts = [b.strip() for b in blocks if b and b.strip()]
    return "\n\n".join(parts)


def append_diagnostics(message: str, diagnostics: str) -> str:
    """Append a diagnostics section to an existing operator message."""
    blob = diagnostics.strip()
    if not blob:
        return message
    return f"{message.rstrip()}\n\n{blob}"


def compose_services_from_failure_text(
    text: str,
    *,
    known_services: Sequence[str] = (),
) -> list[str]:
    """Extract compose service ids mentioned in a compose failure blob."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(service: str) -> None:
        if service and service not in seen:
            seen.add(service)
            found.append(service)

    _add_from_container_names(text, _add)
    _add_known_tokens(text, known_services, _add)
    return found


def _add_from_container_names(text: str, add) -> None:
    for match in _CONTAINER_FAIL_RE.finditer(text or ""):
        name = match.group("name")
        mapped = _PROJECT_CONTAINER_RE.match(name)
        add(mapped.group("service") if mapped else name)


def _add_known_tokens(text: str, known_services: Sequence[str], add) -> None:
    ordered = sorted(known_services, key=len, reverse=True)
    lower = (text or "").lower()
    for service in ordered:
        token = service.lower()
        if token and token in lower:
            add(service)


def prefer_errorish_lines(text: str, *, max_lines: int = 12) -> str:
    """Prefer emerg/error/fatal/traceback lines; else last ``max_lines``."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    markers = ("emerg", "error", "fatal", "traceback", "exception", "panic")
    interesting = [line for line in lines if any(m in line.lower() for m in markers)]
    chosen = interesting[-max_lines:] if interesting else lines[-max_lines:]
    return "\n".join(chosen)


def summarize_health_inspect(
    status: str,
    health: str = "",
    *,
    last_output: str = "",
) -> str:
    """One-line health summary for headers / doctor detail."""
    status = (status or "").strip() or "unknown"
    health = (health or "").strip()
    if health and health != "none":
        summary = f"{status}/{health}"
    else:
        summary = status
    out = (last_output or "").strip()
    if not out:
        return summary
    return f"{summary}; healthcheck: {prefer_errorish_lines(out, max_lines=1)}"
