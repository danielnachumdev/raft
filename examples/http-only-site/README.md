# HTTP-only site

Single Host-routed HTTP port with `tls: off`. No Origin PEMs. Use this for plain
HTTP behind the gate, or when TLS is handled upstream (e.g. Cloudflare Flexible).

## When to use

- One website/API on a public hostname
- No VPS-side HTTPS for this app
- You want the richest field comments in one place (see `.raft/app.yaml`)

## Apply

```bash
# From this tree (adjust source/path if needed):
raft apply --file examples/http-only-site/.raft/app.yaml

# Typical service-repo flow:
raft apply --git git@github.com:example/http-only-site.git
```

Then:

```bash
raft up                 # first bring-up
raft redeploy http-only-site   # later updates
raft doctor
```

Replace `publicHost`, `repo`, and `metadata.name` before a real deploy.
