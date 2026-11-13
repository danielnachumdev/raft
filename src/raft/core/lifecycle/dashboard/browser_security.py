"""Browser security header values for dashboard SPA / static HTML.

HSTS is applied only when the client-facing hop is HTTPS (TLS at the gate
or ``X-Forwarded-Proto: https``). Plain HTTP localhost ``raft serve`` does
not advertise HSTS so operators are not sticky-pinned to https://127.0.0.1.
"""


class BrowserSecurityHeaders:
    """Shared CSP / HSTS / anti-framing values for FastAPI and dashboard nginx."""

    # 180 days — rollout-safe; no includeSubDomains / preload.
    HSTS_MAX_AGE = 15_552_000
    HSTS = f"max-age={HSTS_MAX_AGE}"

    # Packaged Vite SPA: same-origin hashed assets; no third-party scripts.
    CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    # Static login / unauthorized HTML ships inline style (+ login script).
    CSP_INLINE_HTML = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    X_FRAME_OPTIONS = "DENY"
    X_CONTENT_TYPE_OPTIONS = "nosniff"
    REFERRER_POLICY = "strict-origin-when-cross-origin"

    def as_dict(self, *, https: bool, inline_html: bool = False) -> dict[str, str]:
        """Headers for one response; omit HSTS unless ``https``."""
        csp = self.CSP_INLINE_HTML if inline_html else self.CSP
        out = {
            "Content-Security-Policy": csp,
            "X-Frame-Options": self.X_FRAME_OPTIONS,
            "X-Content-Type-Options": self.X_CONTENT_TYPE_OPTIONS,
            "Referrer-Policy": self.REFERRER_POLICY,
        }
        if https:
            out["Strict-Transport-Security"] = self.HSTS
        return out

    def nginx_add_header_lines(self, *, inline_html: bool = False) -> str:
        """``add_header`` block for a location (nginx clears parent add_header)."""
        csp = self.CSP_INLINE_HTML if inline_html else self.CSP
        return (
            f'            add_header Content-Security-Policy "{csp}" always;\n'
            f"            add_header X-Frame-Options {self.X_FRAME_OPTIONS} "
            "always;\n"
            f"            add_header X-Content-Type-Options "
            f"{self.X_CONTENT_TYPE_OPTIONS} always;\n"
            f"            add_header Referrer-Policy "
            f"{self.REFERRER_POLICY} always;\n"
            "            add_header Strict-Transport-Security "
            "$raft_hsts always;\n"
        )

    @staticmethod
    def nginx_hsts_map() -> str:
        """Map edge/TLS proto → HSTS value (empty on plain HTTP)."""
        age = BrowserSecurityHeaders.HSTS_MAX_AGE
        return (
            "    map $raft_fwd_proto $raft_hsts {\n"
            "        default \"\";\n"
            f'        https   "max-age={age}";\n'
            "    }\n"
        )
