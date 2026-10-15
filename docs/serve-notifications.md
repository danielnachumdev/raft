# Serve notifications

Outbound alert channels for this host. Operators manage them under **Settings → Notifications** in `raft serve`. Durable config lives in `~/.raft/settings.yaml` under `notifications:` (not under `state/`).

## Shipped strategies

| `type` | Delivery | Notes |
|--------|----------|--------|
| `webhook` | HTTPS POST JSON | Optional `timeoutSeconds`, `headers`, lab-only `allowInsecureHttp` |
| `email` | Plain-text SMTP | Optional auth / STARTTLS / port / timeout |
| `whatsapp` | [GREEN-API](https://greenapi.com) `sendMessage` | Text alerts to a WhatsApp chat |

The serve API exposes the strategy catalog at `GET /api/notifications/strategies` (includes labels and typed field metadata for the SPA form). Channel CRUD is under `/api/notifications/channels`.

## WhatsApp (GREEN-API)

Create an instance in the GREEN-API console and copy access parameters ([before you start](https://greenapi.com/en/docs/before-start/)). Required channel settings:

| Key | Role |
|-----|------|
| `apiUrl` | API host (HTTPS), e.g. `https://api.green-api.com` |
| `idInstance` | Instance id (string or number; stored as string) |
| `apiTokenInstance` | Instance access key (**secret**) |
| `chatId` | Destination chat, e.g. `79001234567@c.us` or `…@g.us` |

Optional: `timeoutSeconds` (default `10`). `mediaUrl` is not required for text-only delivery.

raft POSTs to:

```text
{apiUrl}/waInstance{idInstance}/sendMessage/{apiTokenInstance}
```

with JSON `{"chatId","message"}` ([SendMessage](https://greenapi.com/en/docs/api/sending/SendMessage/)). Delivery logs only the HTTP status — never the token or full URL.

## Secrets

Secret-like settings keys (`password`, `token`, `apiTokenInstance`, …) are persisted in `settings.yaml` (same stance as SMTP password) and redacted as `***` in serve GET/list responses. Re-saving `***` keeps the stored value (`merge_preserving_secrets`). Do not put live tokens or phone numbers in git fixtures.

## Example (`settings.yaml`)

```yaml
notifications:
  enabled: true
  channels:
    - id: ops-whatsapp
      enabled: true
      type: whatsapp
      settings:
        apiUrl: https://api.green-api.com
        idInstance: "1101000001"
        apiTokenInstance: "replace-me"
        chatId: 79001234567@c.us
```

See also [`examples/settings.yaml`](../examples/settings.yaml).
