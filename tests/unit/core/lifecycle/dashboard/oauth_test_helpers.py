"""Shared helpers for dashboard OAuth unit tests (PII-safe fixtures only)."""

from pathlib import Path

from raft.core.lifecycle.dashboard.oauth_ops import DashboardOAuthOps


def seed_oauth_secrets(home: Path) -> DashboardOAuthOps:
    """Init env + demo client secrets + example.com allowlist identity."""
    settings = home / "settings.yaml"
    if not settings.is_file():
        settings.write_text("{}\n", encoding="utf-8")
    ops = DashboardOAuthOps(home)
    out = ops.init(provider="google")
    _fill_demo_client(Path(out["envFile"]))
    allow = home / "tmp-allow.txt"
    allow.write_text("ops@example.com\n", encoding="utf-8")
    ops.allowlist_set(allow)
    return ops


def _fill_demo_client(env: Path) -> None:
    text = env.read_text(encoding="utf-8")
    env.write_text(
        text.replace("OAUTH2_PROXY_CLIENT_ID=", "OAUTH2_PROXY_CLIENT_ID=demo").replace(
            "OAUTH2_PROXY_CLIENT_SECRET=",
            "OAUTH2_PROXY_CLIENT_SECRET=secret",
        ),
        encoding="utf-8",
    )
