# Grouped volume app

Manifest-only sample: `spec.group`, `spec.envFile`, `spec.volumes`, and an internal-only port (`expose: none`). No public Host routing — other apps in the group reach it on the Compose network.

## When to use

- Sidecars / data services that should not be on the public gate
- Shared operator grouping under one `spec.group`
- Bind mounts and an env file owned by the operator host

## Apply

Replace `image` / `ref`, `envFile`, and volume `hostPath` before a real deploy.

```bash
raft apply --file examples/grouped-volume-app/.raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default. Pair with an edge-facing App in the same `group` when you want a full multi-app stack.
