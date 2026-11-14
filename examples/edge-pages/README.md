# Edge visitor HTML pages

Stock gate pages cover unavailable / forbidden / maintenance / scale-to-zero
holding. Public Host apps can override them with HTML shipped in the App tree
(paths relative to the app root; require `spec.publicHost`).

## Spec keys

| Key | When visitors see it | Default stock |
|-----|----------------------|---------------|
| `unavailablePage` | Upstream 502/503/504 while **not** in a live cutover → HTTP 503 | `unavailable.html` |
| `forbiddenPage` | Ordered edge firewall deny for this Host → HTTP 403 | `forbidden.html` |
| `maintenancePage` | Upstream 502/503 during intentional live apply/redeploy (`STATUS redeploying`) | `maintenance.html` |
| `scaling.holdingPage` | Idle scale-to-zero wake holding (optional under `spec.scaling`) | `holding.html` |

Copy the demo HTML from [`../http-only-site/.raft/`](../http-only-site/.raft/) (`unavailable.html`, `forbidden.html`, `maintenance.html`, `holding.html`) into your service repo, then uncomment the matching keys (see snippet below and [`../http-only-site/.raft/app.yaml`](../http-only-site/.raft/app.yaml)).

## Snippet

Paste under `spec:` (indent to match). Paths are relative to the app root:

```yaml
# Requires publicHost (Host-routed public traffic).
unavailablePage: .raft/unavailable.html
forbiddenPage: .raft/forbidden.html
maintenancePage: .raft/maintenance.html

# Scale-to-zero holding (only with a scaling: block):
# scaling:
#   idleSeconds: 300
#   wakeTimeoutSeconds: 60
#   minUpSeconds: 60
#   holdingPage: .raft/holding.html
```

After the HTML lands in the checkout: `raft apply` (or `raft sync <name> && raft render`) so the gate bind-mount picks up the copies.

## Redeploy vs unavailable

During a live `raft apply` / `raft redeploy <name>` cutover, raft marks the App
`redeploying`. Visitors who hit a failing upstream get **maintenance** (not
unavailable). When the marker clears, the same failure class shows **unavailable**
again. Operator `raft down <name>` is **manual-stop** (intentional; not treated as
not-running) — distinct from cutover maintenance.

Dummy branding only (`demo-api`). Replace copy before a real deploy.
