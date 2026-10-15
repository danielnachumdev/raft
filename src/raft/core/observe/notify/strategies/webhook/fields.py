"""Serve/SPA catalog field metadata for webhook channels."""

from ...catalog_field import CatalogField

FIELDS = [
    CatalogField.define(
        "url",
        label="Webhook URL",
        kind="url",
        required=True,
        help_text="HTTPS endpoint that accepts a JSON POST.",
        placeholder="https://hooks.example.invalid/raft",
    ),
    CatalogField.define(
        "timeoutSeconds",
        label="Timeout (seconds)",
        kind="number",
        required=False,
        placeholder="10",
    ),
    CatalogField.define(
        "allowInsecureHttp",
        label="Allow insecure HTTP",
        kind="checkbox",
        required=False,
        help_text="Lab only — permit http:// URLs.",
    ),
]

LABEL = "Webhook"
