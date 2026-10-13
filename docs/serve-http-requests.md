# Serve: HTTP request inspection

Per-request HTTP details in `raft serve` for Host-routed Apps (`expose: http` + `publicHost`). Complements **Trends → HTTP**, which stays aggregate-only (RPS, latency percentiles, status classes from `http.jsonl`).

Design lock: [issue #197](https://github.com/danielnachumdev/raft/issues/197).

## Where it appears

- Service detail (`/service/<compose-id>`), panel **HTTP requests**.
- Hidden for gate / router / controller, workers, and stream/host/none-only Apps.
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

## API

`GET /api/service/{name}/http-requests?limit=100`

Returns recent rows for that App’s `publicHost` + `extraHosts` (newest first). Ineligible services return `eligible: false` and an empty `requests` list (unknown name → 404).

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

## Out of scope

- ACL whitelist/blacklist management (#195)
- Add/remove client IP actions from a request row (#198)
