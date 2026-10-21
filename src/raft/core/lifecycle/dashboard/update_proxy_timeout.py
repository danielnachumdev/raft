"""Shared proxy budget for Settings → Update through the dashboard.

Gate TLS, router Host server, and in-container nginx must use the same
value. A shorter hop aborts the browser (nginx 499) while install.sh runs.
"""

# Docker one-shot image pull + install.sh; keep HostOneshot sync Update timeout aligned.
UPDATE_PROXY_TIMEOUT_SECONDS = 600
UPDATE_PROXY_TIMEOUT = f"{UPDATE_PROXY_TIMEOUT_SECONDS}s"
