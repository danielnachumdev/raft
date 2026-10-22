# AGENTS.md — scripts/hosts

Temporarily map applied App `publicHost` / `extraHosts` values to `127.0.0.1` so browsers hit the local gate. Always restores on exit.

| File | Role |
|------|------|
| [hosts.py](hosts.py) | CLI entry (`hold` / `run`) |
| [hosts_plan.py](hosts_plan.py) | Bindings from applied Apps or `--entry` |
| [hosts_session.py](hosts_session.py) | Apply / restore session |
| [hosts_windows.py](hosts_windows.py) | WSL → Windows hosts + DNS flush |

```bash
sudo python3 scripts/hosts/hosts.py hold
sudo python3 scripts/hosts/hosts.py run -- curl -I https://app.example.test/
sudo python3 scripts/hosts/hosts.py --entry 127.0.0.1,app.example.test hold
```

Targets: Linux `/etc/hosts`; on WSL also Windows `drivers/etc/hosts` (unless `--linux-only` / `--windows-only`).
