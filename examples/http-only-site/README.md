# HTTP-only site

Single Host-routed HTTP port with `tls: off`. No Origin PEMs. Use this for plain
HTTP behind the gate, or when TLS is handled upstream (e.g. Cloudflare Flexible).

## When to use

- One website/API on a public hostname
- No VPS-side HTTPS for this app
- You want the richest field comments in one place (see `.raft/app.yaml`)

## Apply (recommended)

Deploy is **on** by default. One command covers first boot and later cutovers:

```bash
# From this tree (adjust source/path if needed):
raft apply --file examples/http-only-site/.raft/app.yaml

# Typical service-repo / CI flow (pin the commit):
raft apply --file .raft/app.yaml --ref "$SHA" --env KEY=value
# or: raft apply --git git@github.com:example/http-only-site.git --ref "$SHA"
```

Then: `raft doctor`.

Optional: if the app Compose service is **already running** and you only want
cutover without re-applying the manifest, `raft redeploy http-only-site --ref "$SHA"`.
Do not use `--no-deploy` + `redeploy` for a new App — `redeploy` fails when the
service is not up yet.

Replace `publicHost`, `repo`, and `metadata.name` before a real deploy.
