# Serve operator settings

Edit the full host document `~/.raft/settings.yaml` (`RaftConfig`) from **Settings** in `raft serve`, or via `GET` / `PUT /api/settings`.

Specialized pages remain for deep workflows:

| UI | Durable state |
|----|----------------|
| **Settings** (this page) | Full `settings.yaml` sections |
| Settings → Updates | Host CLI package (GitHub Releases); not in `settings.yaml` |
| Settings → Notifications | Channel CRUD (`notifications.channels`) |
| Settings → Alerts | Rules under `state/alerts/rules.yaml` |
| Settings → Firewall | Ordered rules under `state/firewall/rules.yaml` |
| Settings → Storage | Host cleanup (`POST /api/purge` / `raft purge`) — not in `settings.yaml` |

## Updates (Check for updates)

**Settings → Updates** queries GitHub for the latest raft Release (same SoT as `raft update` / `install.sh` — prefer Release wheel) and compares it to the installed package version.

| Action | API | Behavior |
|--------|-----|----------|
| Check for updates | `GET /api/update/status` | Latest Release tag vs installed semver |
| Update raft | `POST /api/update` | Runs the shared `SelfUpdate` path (`install.sh`); optional JSON `{ "ref": "<tag\|branch\|sha>" }` matches CLI `--ref` |

Confirm before apply. After a successful update, align the running stack the same way as CLI (`raft render` / targeted `redeploy` / `down`+`up` when schemas shifted, then `raft doctor`). Restart `raft serve` or the dashboard process so the UI loads the new package.

## Sections

| Section | Role | Side effects |
|---------|------|----------------|
| Appearance | Dashboard light/dark theme | Browser `localStorage` only; applies immediately (not in `settings.yaml`) |
| Updates (UI) | Check / apply raft package updates | Reinstalls CLI via `install.sh`; stack may need render/redeploy |
| `logging` | Host CLI file log | Applies on next CLI process |
| `edge` | Gate published http / https / streams | **Ports change → `raft gate recreate`** |
| `healing` | Controller self-heal | Next heal job tick |
| `metrics` | Resource + HTTP sampling | Next metrics job tick |
| `serviceLogs` | Retained Compose stdout | Next shipper tick |
| `acme` | Let's Encrypt HTTP-01 | Apply/renew jobs; email required when apps use `tls: acme` |
| `github` | Serve OAuth (Add from GitHub) | `RAFT_GITHUB_*` env overrides when set |
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

Update check / apply (not part of the settings document):

```http
GET /api/update/status
POST /api/update
Content-Type: application/json

{ "ref": "v0.12.0" }
```

`GET` returns camelCase fields: `current`, `currentLine`, `latestTag`, `latestVersion`, `updateAvailable`, `releaseUrl`, `state`, `message`. `POST` returns `alreadyCurrent`, `beforeLine`, `afterLine`, `nextSteps`.

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
