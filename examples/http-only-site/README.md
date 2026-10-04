# HTTP-only site

One Host-routed HTTP port with `tls: off`. No Origin PEMs on the VPS. Use when the app is plain HTTP behind the gate, or when TLS is terminated upstream of this host.

## When to use

- One website or API on a public hostname
- No host-side HTTPS for this app
- You want the richest commented manifest in one place (resources, optional scaling)

Optional scale-to-zero via apply-time `${{ if }}`: see [`optional-block.snippet.yaml`](optional-block.snippet.yaml). Broader preprocess docs: [`docs/app-manifest.md`](../../docs/app-manifest.md).

## Apply

Deploy is **on** by default (first boot and later cutovers):

```bash
raft apply --file examples/http-only-site/.raft/app.yaml --ref "$SHA"
# Typical service-repo / CI:
# raft apply --file .raft/app.yaml --ref "$SHA" --env KEY=value
raft doctor
```

Replace `publicHost`, `repo`, and `metadata.name` before a real deploy.

`raft redeploy` is only for an app service that is **already running** when you want cutover without rewriting the registry. Do not use `--no-deploy` + `redeploy` for a new App.
