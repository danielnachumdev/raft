# HTTP-only site

One Host-routed HTTP port with `tls: off`. No Origin PEMs on the VPS. Use when the app is plain HTTP behind the gate, or when TLS is terminated upstream of this host.

## When to use

- One website or API on a public hostname
- No host-side HTTPS for this app
- You want the richest commented manifest in one place (resources, optional scaling, edge HTML overrides)

Optional scale-to-zero via apply-time `${{ if }}`: see [`optional-block.snippet.yaml`](optional-block.snippet.yaml). Preprocess, name↔source, and secrets notes are in the `app.yaml` header comments.

## Edge visitor pages

Commented keys in [`.raft/app.yaml`](.raft/app.yaml) (`unavailablePage`, `forbiddenPage`, `maintenancePage`, plus `scaling.holdingPage`). Demo HTML (dummy `demo-api` copy):

- [`.raft/unavailable.html`](.raft/unavailable.html) — upstream down outside a live cutover
- [`.raft/forbidden.html`](.raft/forbidden.html) — firewall deny
- [`.raft/maintenance.html`](.raft/maintenance.html) — intentional apply/redeploy cutover
- [`.raft/holding.html`](.raft/holding.html) — scale-to-zero wake

Operator primer + pasteable snippet: [`../edge-pages/`](../edge-pages/).

## Apply

Deploy is **on** by default (first boot and later cutovers):

```bash
raft apply --file examples/http-only-site/.raft/app.yaml --ref "$SHA"
# Typical service-repo / CI:
# raft apply --file .raft/app.yaml --ref "$SHA" --env KEY=value
raft doctor
```

Replace `publicHost`, `repo`, and `metadata.name` before a real deploy.

`raft redeploy <name>` refreshes an **already-applied** unit (cutover when live; may start when down). Do not use `--no-deploy` + `redeploy` as the happy path for a new App — use `raft apply`.
