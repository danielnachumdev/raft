# Serve operator settings

Edit the full host document `~/.raft/settings.yaml` (`RaftConfig`) from **Settings** in `raft serve`, or via `GET` / `PUT /api/settings`.

Specialized pages remain for deep workflows:

| UI | Durable state |
|----|----------------|
| **Settings** (this page) | Full `settings.yaml` sections |
| Settings → Notifications | Channel CRUD (`notifications.channels`) |
| Settings → Alerts | Rules under `state/alerts/rules.yaml` |
| Settings → Firewall | Ordered rules under `state/firewall/rules.yaml` |
| Settings → Storage | Host cleanup (`POST /api/purge` / `raft purge`) — not in `settings.yaml` |

## Sections

| Section | Role | Side effects |
|---------|------|----------------|
| `logging` | Host CLI file log | Applies on next CLI process |
| `edge` | Gate published http / https / streams | **Ports change → `raft gate recreate`** |
| `healing` | Controller self-heal | Next heal job tick |
| `metrics` | Resource + HTTP sampling | Next metrics job tick |
| `serviceLogs` | Retained Compose stdout | Next shipper tick |
| `acme` | Let's Encrypt HTTP-01 | Apply/renew jobs; email required when apps use `tls: acme` |
| `github` | Serve OAuth / mock | `RAFT_GITHUB_*` env overrides when set |
| `notifications` | Global enable + channels | Channel secrets redacted in API; prefer Notifications page for CRUD |
| `alerts` | Evaluation cadence | Rules stay under `state/alerts/` |
| Storage | Purge unused Docker images / build cache | Confirm → `POST /api/purge` (same as `raft purge`); toasts for success/error |

Legacy `acl.gate` may still appear in the API document for round-trip and migrate-on-GET into Firewall until Save — it is **not** an editable Settings section. Prefer [Settings → Firewall](serve-firewall.md).

## API

```http
GET /api/settings
PUT /api/settings
Content-Type: application/json

{ "document": { "logging": {…}, "edge": {…}, … } }
```

Response shape:

```json
{
  "path": "/tmp/raft-demo/home/settings.yaml",
  "document": { },
  "notes": [
    {
      "code": "edge.ports",
      "severity": "warn",
      "message": "Published edge ports … Run `raft gate recreate` …"
    }
  ]
}
```

Validation uses the same section parsers as file load. Secret-like values (`github.clientSecret`, notification channel tokens/passwords) are returned as `***`; re-saving the mask keeps the stored value.

Mutative writes take `settings.lock` (same flock as notification channel and GitHub OAuth settings writers).

## PII

Fixtures, docs, and screenshots use only documentation hosts (`ops.example.com`, `*.demo.example`), `ops@example.com`, `demo-api`, and `192.0.2.0/24`.

## Related

- [`examples/settings.yaml`](../examples/settings.yaml)
- [`serve-notifications.md`](serve-notifications.md)
- [`serve-alerts.md`](serve-alerts.md)
- [`serve-firewall.md`](serve-firewall.md)
- [`serve-acl.md`](serve-acl.md) (legacy)
