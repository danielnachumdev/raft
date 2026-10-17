# Serve notifications

Outbound alert channels for this host. Operators manage them under **Settings → Notifications** in `raft serve`, or via **`raft notifications …`** (same shared core service: `NotificationsSettingsWriter` / `NotificationsTester`). Durable config lives in `~/.raft/settings.yaml` under `notifications:` (not under `state/`).

## Alert rules

Rules that decide *when* to notify live separately under **Settings → Alerts** / `raft alerts` (`state/alerts/rules.yaml`). They emit into these channels (optional per-rule `channelIds`; empty means all enabled channels). See [`serve-alerts.md`](serve-alerts.md).

## Shipped strategies

| `type` | Delivery | Notes |
|--------|----------|--------|
| `webhook` | HTTPS POST JSON | Optional `timeoutSeconds`, `headers`, lab-only `allowInsecureHttp` |
| `email` | Plain-text SMTP | Optional auth / STARTTLS / port / timeout |
| `whatsapp` | [GREEN-API](https://greenapi.com) `sendMessage` | Text alerts to a WhatsApp chat |

The serve API exposes the strategy catalog at `GET /api/notifications/strategies` (includes labels and typed field metadata for the SPA form). Channel CRUD is under `/api/notifications/channels`. Probe a channel with `POST /api/notifications/channels/{id}/test` (SPA **Send test**) or `raft notifications test <id>`.

## CLI

| Command | Role |
|---------|------|
| `raft notifications list` / `show ID` | List/show channels (secrets as `***`) |
| `raft notifications strategies` | Strategy catalog |
| `raft notifications create --file channel.yaml` | Create (same body as serve POST) |
| `raft notifications update ID --file patch.yaml` | Update / merge settings |
| `raft notifications enable\|disable ID` | Toggle `enabled` |
| `raft notifications delete ID` | Remove channel |
| `raft notifications test ID` | Safe probe through `Notifier` strategies |

Example create file (PII-safe fixture names only):

```yaml
id: ops-webhook
type: webhook
enabled: true
settings:
  url: https://example.invalid/hooks/demo-api
```

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
