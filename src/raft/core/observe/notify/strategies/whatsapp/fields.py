"""Serve/SPA catalog field metadata for WhatsApp (GREEN-API)."""

from ...catalog_field import CatalogField

FIELDS = [
    CatalogField.define(
        "apiUrl",
        label="API URL",
        kind="url",
        required=True,
        help_text="GREEN-API console apiUrl (HTTPS host).",
        placeholder="https://api.green-api.com",
    ),
    CatalogField.define(
        "idInstance",
        label="Instance ID",
        kind="text",
        required=True,
        help_text="GREEN-API console idInstance.",
        placeholder="1101000001",
    ),
    CatalogField.define(
        "apiTokenInstance",
        label="API token",
        kind="secret",
        required=True,
        help_text="GREEN-API console apiTokenInstance (secret).",
    ),
    CatalogField.define(
        "chatId",
        label="Chat ID",
        kind="text",
        required=True,
        help_text="Destination WhatsApp chat, e.g. 79001234567@c.us or group@g.us.",
        placeholder="79001234567@c.us",
    ),
    CatalogField.define(
        "timeoutSeconds",
        label="Timeout (seconds)",
        kind="number",
        required=False,
        placeholder="10",
    ),
]

LABEL = "WhatsApp (GREEN-API)"
