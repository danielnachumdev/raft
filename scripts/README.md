# scripts/

Operator helpers that are not part of the `raft` CLI package.

## `hosts.py`

Temporarily maps applied App `publicHost` values to `127.0.0.1` in the local hosts file(s), then **always** restores the previous contents on exit (Ctrl+C, signal, or command finish).

### What it is for

Raft’s gate routes by `Host`. On a laptop/WSL box you often hit `http://127.0.0.1/` while Cloudflare DNS still points at the VPS. Without a hosts entry (or an explicit `curl -H 'Host: …'`), the browser sends the wrong hostname and the router will not select your app.

`hosts` reads applied manifests under `~/.raft/state/apps/*.yaml` (or `RAFT_DATA_HOME`), collects each `publicHost` (and a `www.` alias when missing), and injects a managed block into:

- Linux: `/etc/hosts`
- Windows (from WSL, when present): `/mnt/c/Windows/System32/drivers/etc/hosts`

If no apps are applied, it errors — apply an App first, or pass `--entry`.

### Usage

```bash
# Hold mappings until Ctrl+C (needs write access / sudo on Linux)
sudo python3 scripts/hosts.py hold

# Patch only for the duration of a command
sudo python3 scripts/hosts.py run -- curl -I https://example.test/

# Explicit entries instead of applied apps
sudo python3 scripts/hosts.py --entry 127.0.0.1,app.example.test hold

# Linux-only or Windows-only
sudo python3 scripts/hosts.py --linux-only hold
python3 scripts/hosts.py --windows-only hold
```

Typical local check without this script:

```bash
curl -H 'Host: <publicHost>' http://127.0.0.1/
```

### Notes

- Prefer `hold` while iterating in a browser; use `run` for one-shot probes.
- On WSL, Windows writes may prompt for UAC elevation.
- Do not leave a managed block behind: exit cleanly so restore runs. Markers look like `# >>> raft hosts BEGIN` … `# <<< raft hosts END`.
