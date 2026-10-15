"""Serve/SPA catalog field metadata for email channels."""

from ...catalog_field import CatalogField

FIELDS = [
    CatalogField.define(
        "to",
        label="To",
        kind="text",
        required=True,
        placeholder="ops@example.com",
    ),
    CatalogField.define(
        "from",
        label="From",
        kind="text",
        required=True,
        placeholder="raft@example.com",
    ),
    CatalogField.define(
        "smtpHost",
        label="SMTP host",
        kind="text",
        required=True,
        placeholder="smtp.example.com",
    ),
    CatalogField.define(
        "smtpPort",
        label="SMTP port",
        kind="number",
        required=False,
        placeholder="587",
    ),
    CatalogField.define(
        "username",
        label="Username",
        kind="text",
        required=False,
    ),
    CatalogField.define(
        "password",
        label="Password",
        kind="secret",
        required=False,
        help_text="Required when username is set. Redacted after save.",
    ),
    CatalogField.define(
        "useStartTls",
        label="Use STARTTLS",
        kind="checkbox",
        required=False,
        help_text="Default true when omitted.",
    ),
    CatalogField.define(
        "timeoutSeconds",
        label="Timeout (seconds)",
        kind="number",
        required=False,
        placeholder="10",
    ),
]

LABEL = "Email"
