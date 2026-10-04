# scripts/

Small operator helpers that are **not** part of the `raft` CLI. Today that means one tool: local `Host` routing for browser checks.

## The problem

raft’s gate routes by `Host`. When you hit `http://127.0.0.1/` on a local machine, the browser sends that hostname — not your app’s `publicHost` — so the router never selects the right upstream.

You can always probe with an explicit header:

```bash
curl -H 'Host: <publicHost>' http://127.0.0.1/
```

Browsers don’t. That’s what `hosts.py` is for.

## What `hosts.py` does

Reads applied Apps under `~/.raft/state/apps/` (or `RAFT_DATA_HOME`), collects each `publicHost` (plus a `www.` alias when missing), and temporarily maps them to `127.0.0.1` in the local hosts file(s). On exit — Ctrl+C, signal, or command finish — it **always** restores the previous contents.

Targets:

- Linux: `/etc/hosts`
- Windows (from WSL, when present): `/mnt/c/Windows/System32/drivers/etc/hosts`

If nothing is applied, it errors — apply an App first, or pass `--entry`.

## Try it

```bash
# Hold mappings until Ctrl+C (needs write access / sudo on Linux)
sudo python3 scripts/hosts.py hold

# Patch only for the duration of a command
sudo python3 scripts/hosts.py run -- curl -I https://app.example.test/

# Explicit entries instead of applied apps
sudo python3 scripts/hosts.py --entry 127.0.0.1,app.example.test hold
```

Linux-only or Windows-only:

```bash
sudo python3 scripts/hosts.py --linux-only hold
python3 scripts/hosts.py --windows-only hold
```

## Notes

- Prefer `hold` while clicking around in a browser; use `run` for one-shot probes.
- On WSL, Windows writes may prompt for UAC elevation.
- Exit cleanly so restore runs. Managed markers look like `# >>> raft hosts BEGIN` … `# <<< raft hosts END`.
