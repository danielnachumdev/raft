# Dashboard SPA (React + Vite + TypeScript)

Source for the `raft serve` UI. **Runtime is static only**: `npm run build`
writes into `src/raft/share/serve/spa/`, which FastAPI serves from the same
process as `/api/status` and `/api/metrics`. There is no separate Node server
in production. Trends charts poll `/api/metrics` (with a `since` cursor) rather
than opening a WebSocket.

## Develop

```bash
cd web
npm ci
npm run dev          # Vite on :5173; proxies /api → raft serve :8787
```

In another terminal: `raft serve` (or `uv run raft serve`).

## Release / commit FE changes

```bash
cd web
npm ci
npm run build        # updates ../src/raft/share/serve/spa/
```

Commit the updated `spa/` assets with the Python package so
`uv tool install` / `raft update` ships a working UI without Node on the VM.
