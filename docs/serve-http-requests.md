# Serve: HTTP request inspection

Per-request HTTP details in `raft serve` for Host-routed Apps (`expose: http` + `publicHost`). Complements **Trends → HTTP**, which stays aggregate-only (RPS, latency percentiles, status classes from `http.jsonl`).

Design lock: [issue #197](https://github.com/danielnachumdev/raft/issues/197).

## Where it appears

- Service detail (`/service/<compose-id>`), panel **HTTP requests**.
- Hidden for gate / router / controller / dashboard, workers, and stream/host/none-only Apps.
- Not an edge-wide request browser in v1.

## Source of truth

Gate access log (bind-mounted):

`~/.raft/state/metrics/gate-http/access.log`

Enriched `log_format` (product template `nginx/gate/nginx.conf`):

```text
$request_time $status $host $time_iso8601 $request_method $uri $remote_addr "$http_user_agent"
```

- First three fields unchanged so the controller aggregate scrape → `http.jsonl` keeps working.
- Path is `$uri` only (no query string).
- Cookies, `Authorization`, and bodies are never logged.
- New fields appear after share sync and a gate nginx **reload** (config file change).

## API and CLI

`GET /api/service/{name}/http-requests?limit=100`

Returns recent rows for that App’s `publicHost` + `extraHosts` (newest first). Ineligible services return `eligible: false` and an empty `requests` list (unknown name → 404).

CLI (same `HttpRequestsRead` contract):

```bash
raft http_requests show demo-api --limit=50
raft http_requests show demo-api --json
```

Deny a client from a row (shared firewall from-inspection path):

```bash
raft firewall apply_inspection --client-ip=192.0.2.10 --service=demo-api
```

## Privacy defaults

| Concern | Default |
|---------|---------|
| Query strings | Omitted at source |
| Cookies / auth / bodies | Never logged |
| Path / User-Agent length | Capped in the API response |

Fixtures and docs use dummy names only (`demo-api`, `demo-api.test`, `192.0.2.10`).

## Empty and special states

| State | Behavior |
|-------|----------|
| No matching rows | “No recent HTTP requests for this service.” |
| Scaled to zero | Panel still shown; note that traffic will wake the App |
| Not running | Panel still shown for leftover log rows |
| Ineligible | Panel hidden |

## Firewall from a request row (#198)

When a row has `client_ip`, operators can **Firewall** (add/update) or **Remove** an ordered edge rule for that client:

| Prefill | Source |
|---------|--------|
| CIDR | Client IP as host `/32` or `/128` (expandable in the form) |
| Service | App name for this Host-routed service |
| Port / protocol | Preferred edge listen (`https` then `http`) / `tcp` |
| Action | Operator chooses `deny` \| `permit` \| `drop` |

**Insert order:** new/updated rules are **prepended** (top of the ordered table) so they evaluate before broad `permit any` / default-deny. Apply uses the same #211 persist → render → gate nginx reload path (`POST /api/firewall/from-inspection`). Remove deletes rules whose CIDR equals that host network (`POST /api/firewall/from-inspection/remove`).

Full firewall table UX: Settings → Firewall ([`serve-firewall.md`](serve-firewall.md)).
