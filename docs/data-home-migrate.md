# Data-home layout migrate (#313)

**Breaking.** After the layout release (`bumpMinor`), raft reads and writes
**only** `host/` + `services/<SERVICE>/` under `RAFT_DATA_HOME`. There is no
dual-read of the old tree.

PII-safe example service: `demo-api`.

## One-time operator steps

1. Stop mutative work (`raft down`; stop `raft serve` / controller as needed).
2. Backup the entire `RAFT_DATA_HOME` (default `~/.raft`).
3. Upgrade raft to the layout release.
4. Migrate paths (pick one):
   - `raft migrate --dry-run` then `raft migrate`
   - or move manually using the tables on
     [issue #313](https://github.com/danielnachumdev/raft/issues/313)
5. Confirm: `host/` + `services/<name>/` + `generated/`; remove empty old
   `state/`, top-level `secrets/<app>/`, `certs/`, `apps/`, `deploy/`, `logs/`
   once doctor is clean.
6. Smoke: `raft doctor`, `raft status`, serve UI.
7. Do not hand-edit `generated/`.

`raft doctor` **fails** if old roots remain (e.g. `state/apps/`, root
`settings.yaml`, top-level `secrets/<app>/`). It does not auto-heal by reading
old locations.

## Quick map (demo-api)

| Old | New |
|-----|-----|
| `settings.yaml` | `host/settings.yaml` |
| `state/apps/demo-api.yaml` | `services/demo-api/app.yaml` |
| `secrets/demo-api/**` | `services/demo-api/secrets/**` |
| `certs/demo-api/**` | `services/demo-api/certs/**` |
| `apps/demo-api/**` | `services/demo-api/checkout/**` |
| `deploy/demo-api/**` | `services/demo-api/deploy/**` |
| `state/firewall/**` | `host/firewall/**` |
| `state/alerts/**` | `host/alerts/**` |
| `state/events/**` | `host/events/**` |
| `state/metrics/**` | `host/metrics/**` |
| `state/locks/**` | `host/locks/**` |
| `state/acme/account.*` + `http-01/` | `host/acme/…` |
| `state/acme/apps/demo-api.json` | `services/demo-api/acme/state.json` |
| `state/scaling/demo-api.json` | `services/demo-api/scaling/state.json` |
| `state/scaling/markers/*demo-api*` | `services/demo-api/scaling/markers/` |
| `state/service-logs/<key→demo-api>/**` | `services/demo-api/logs/**` |
| `state/service-logs/<edge-id>/**` | `host/logs/services/<edge-id>/**` |
| `state/serve/**` | `host/serve/**` |
| `secrets/dashboard/**` | `host/secrets/dashboard/**` |
| `logs/**` | `host/logs/**` |
| `state/*-nginx.fingerprint` | `host/*-nginx.fingerprint` |
| `generated/**`, `compose.yaml` | unchanged |

Full table: issue #313.
