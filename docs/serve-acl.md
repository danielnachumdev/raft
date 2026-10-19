# Serve access control (IP/CIDR ACL) — retired

> **Removed as an operator path.** Edge policy is the ordered firewall only.
> See [`docs/serve-firewall.md`](serve-firewall.md).

The flat gate / per-App allow/deny lists (`acl.gate`, `state/acl/apps/`, `/api/acl/*`, Settings UI, service **Access control**) are no longer exposed. Operators edit edge policy only under **Settings → Firewall**.

If leftover `#195` data remains on disk and no `state/firewall/rules.yaml` exists yet, `GET /api/firewall` still shows an in-memory migration (`source: acl-v1-migrated`) until Save. Render always uses firewall includes. `GET`/`PUT /api/settings` may still round-trip leftover `acl.gate` without offering an editor.
