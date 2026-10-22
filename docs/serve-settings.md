# Serve operator settings

Edit the full host document `~/.raft/host/settings.yaml` (`RaftConfig`) from **Settings** in `raft serve`, or via `GET` / `PUT /api/settings` (JSON) and `GET` / `PUT /api/settings/yaml` (YAML text).

Specialized pages remain for deep workflows:

| UI | Durable state |
|----|----------------|
| **Settings** (this page) | Full `settings.yaml` sections |
| Settings → Updates | Host CLI package (GitHub Releases); not in `settings.yaml` |
| Settings → Notifications | Channel CRUD (`notifications.channels`) |
| Settings → Alerts | Rules under `host/alerts/rules.yaml` |
| Settings → Firewall | Ordered rules under `host/firewall/rules.yaml` |
| Settings → Storage | Host cleanup (`POST /api/purge` / `raft purge`) — not in `settings.yaml` |

## Updates (Check for updates)

**Settings → Updates** queries GitHub for the latest raft Release (same SoT as `raft update` / `install.sh` — prefer Release wheel) and compares it to the installed package version.

| Action | API | Behavior |
|--------|-----|----------|
| Check for updates | `GET /api/update/status` | Latest Release tag vs installed semver; includes `canApply` / `applyBlockReason` |
| Update raft | `POST /api/update` | Runs the shared `SelfUpdate` path (`install.sh`); optional JSON `{ "ref": "<tag\|branch\|sha>" }` matches CLI `--ref` |

**Always-on dashboard:** Check works inside `raft-dashboard` (GitHub Release API). **Update** uses the shared `HostOneshot` runner (sync; dashboard has `docker.sock` + `RAFT_HOST_HOME`) so `install.sh` writes into the operator’s host uv-tool env — same outcome as SSH + `raft update`. The one-shot image is `buildpack-deps:bookworm-scm` (needs `git` for `install.sh`). Gate + router + in-container nginx allow **600s** for Settings → Update (pull + install); a 60s gate timeout aborts the browser mid-apply. Apply is blocked only when `RAFT_HOST_HOME`, the Docker socket, or the `docker` CLI is missing (`canApply` / `applyBlockReason`). Host `raft serve` / CLI still apply in-process (curl pipeline). Progress / failures are logged under `raft.core.observe.ops.update` in `host/logs/raft.log`. The same one-shot primitive detaches dashboard **self-Redeploy** (`HostOneshot.start` → 202); see [`docs/serve-dashboard.md`](serve-dashboard.md).

Confirm before apply (when `canApply`). After a successful update, align the running stack the same way as CLI (`raft render` / targeted `redeploy` / `down`+`up` when schemas shifted, then `raft doctor`). When the always-on dashboard is enabled, `raft redeploy dashboard` rebuilds its image with the new install stamp (do not flip `dashboard.enabled`); restart `raft serve` if you use it.

## Form ↔ YAML

The Settings page toggles **Form** and **YAML**:

- **Form** — one card per RaftConfig section with enablement (below). A sticky section index (General / Platform / Integrations / Maintenance, plus links to the Alert rules, Notification channels, and Firewall pages) tracks the scroll position and marks disabled sections **off**. Deep links like `/settings#settings-notifications` jump to a card.
- **YAML** — full document editor. Encode/decode round-trips through `OperatorSettingsService` (`POST /api/settings/yaml/encode` / `decode`); Save uses `PUT /api/settings/yaml`.

**Save** is enabled only when the draft differs from the loaded document. A sticky **Unsaved changes** bar offers Discard (reload from disk) and Save. The browser also asks for confirmation before you close the tab with unsaved edits. Firewall uses the same bar for unsaved rule edits.

Validation always uses the same section parsers as file load. Invalid YAML or sections return OperatorError-style `400` detail.

## Section enablement

GET responses include `sections[]` describing how each block maps to real config (no fake flags that rewrite unrelated keys):

| key | kind | Enabled when |
|-----|------|----------------|
| `logging` | `always` | Always present |
| `edge` | `always` | Always present |
| `metrics` | `always` | Always present (no `enabled` key in RaftConfig) |
| `healing` | `flag` | `healing.enabled` |
| `serviceLogs` | `flag` | `serviceLogs.enabled` |
| `notifications` | `flag` | `notifications.enabled` |
| `alerts` | `flag` | `alerts.enabled` |
| `dashboard` | `flag` | `dashboard.enabled` |
| `acme` | `derived` | `acme.email` is set |
| `github` | `derived` | `github.clientId` is set |

UI behavior:

- **Disabled** sections show an enable toggle; fields are inactive until enabled.
- Enabling a **flag** section sets the corresponding `enabled: true`.
- Enabling **derived** sections leaves real keys for the operator to fill (e.g. ACME email, GitHub `clientId`). Disabling clears presence keys (`acme.email`, GitHub credentials).
- Save rejects incomplete enabled sections client-side (e.g. ACME without email; dashboard `publicHost` with `auth.mode: none`); the backend still validates the full document.

Appearance, Updates, and Storage are UI-only (not `settings.yaml` sections).

## Sections (roles)

| Section | Role | Side effects |
|---------|------|----------------|
| Appearance | Dashboard light/dark theme | Browser `localStorage` only; applies immediately (not in `settings.yaml`) |
| Updates (UI) | Check / apply raft package updates | Reinstalls CLI via `install.sh`; stack may need render/redeploy |
| `logging` | Host CLI file log | Applies on next CLI process |
| `edge` | Gate published http / https / streams | **Ports change → `raft redeploy gate`** |
| `healing` | Controller self-heal | Next heal job tick |
| `metrics` | Resource + HTTP sampling | Next metrics job tick |
| `serviceLogs` | Retained Compose stdout | Next shipper tick |
| `acme` | Let's Encrypt HTTP-01 | Apply/renew jobs; email when enabled / apps use `tls: acme` |
| `github` | Serve OAuth (Add from GitHub) | `RAFT_GITHUB_*` env overrides when set |
| `notifications` | Global enable + channels | Channel secrets redacted; prefer Notifications page for CRUD |
| `alerts` | Evaluation cadence | Rules stay under `host/alerts/` |
| `dashboard` | Always-on `raft-dashboard` | Compose / public Host / auth — see [`serve-dashboard.md`](serve-dashboard.md) |
| Storage | Purge unused Docker images / build cache | Confirm → `POST /api/purge` (same as `raft purge`); toasts for success/error |

Edge IP policy is **not** configured here — use [Settings → Firewall](serve-firewall.md). A leftover `acl:` key in `settings.yaml` is ignored on load and stripped on the next Settings save.

## API

```http
GET /api/settings
PUT /api/settings
Content-Type: application/json

{ "document": { "logging": {…}, "edge": {…}, "dashboard": {…}, … } }

GET /api/settings/yaml
PUT /api/settings/yaml
Content-Type: application/json

{ "yaml": "logging:\n  level: INFO\n…" }

POST /api/settings/yaml/encode
{ "document": { … } }   → { "yaml": "…", "document": {…}, "sections": […] }

POST /api/settings/yaml/decode
{ "yaml": "…" }         → { "document": {…}, "sections": […] }
```

Update check / apply (not part of the settings document):

```http
GET /api/update/status
POST /api/update
Content-Type: application/json

{ "ref": "v0.12.0" }
```

`GET` returns camelCase fields: `current`, `currentLine`, `latestTag`, `latestVersion`, `updateAvailable`, `releaseUrl`, `state`, `message`, `canApply`, `applyBlockReason`. `POST` returns `alreadyCurrent`, `beforeLine`, `afterLine`, `nextSteps` (refuses with 400 when `canApply` would be false).

Response shape (GET/PUT JSON and YAML):

```json
{
  "path": "/tmp/raft-demo/home/host/settings.yaml",
  "document": { },
  "sections": [
    {
      "key": "healing",
      "title": "Healing",
      "kind": "flag",
      "enabled": false,
      "source": "healing.enabled"
    }
  ],
  "notes": [
    {
      "code": "edge.ports",
      "severity": "warn",
      "message": "Published edge ports … Run `raft redeploy gate` …"
    }
  ],
  "yaml": "…"
}
```

(`yaml` is present on `GET /api/settings/yaml` and YAML PUT responses.)

Secret-like values (`github.clientSecret`, `dashboard.auth.passwordHash`, notification channel tokens/passwords) are returned as `***`; re-saving the mask keeps the stored value.

Mutative writes take `settings.lock` (same flock as notification channel and GitHub OAuth settings writers).

## PII

Fixtures, docs, and screenshots use only documentation hosts (`ops.example.com`, `*.demo.example`), `ops@example.com`, `demo-api`, and `192.0.2.0/24`.

## Related

- [`examples/settings.yaml`](../examples/settings.yaml)
- [`serve-dashboard.md`](serve-dashboard.md)
- [`serve-notifications.md`](serve-notifications.md)
- [`serve-alerts.md`](serve-alerts.md)
- [`serve-firewall.md`](serve-firewall.md)
