# Dashboard SPA

Source for the `raft serve` UI (React + Vite + TypeScript).

**Runtime is static only.** `npm run build` writes into [`src/raft/core/platform/share/serve/spa/`](../raft/core/platform/share/serve/spa/), which FastAPI serves from the same process as `/api/status` and `/api/metrics`. There is no separate Node server in production. Trends charts poll `/api/metrics` (Resources) or `/api/metrics/http` (HTTP edge) with a `since` cursor — no WebSocket.

**Status freshness:** the dashboard polls `GET /api/status` every `STATUS_POLL_MS` (**2s**) while the tab is visible. The API re-reads applied Apps from `services/` on each request, so CLI/CI apply/update/delete (including no-port workers) appears within about one poll interval without restarting `raft serve` or hard-refreshing the browser.

Source layout under `src/`: `main.tsx` + `styles.css`, which only imports the global design system from `styles/` (`tokens`, `base`, `buttons`, `forms`, `surfaces`); each UI component imports a co-located `ComponentName.css` for layout only. Use the shared primitives instead of restyling controls per feature: buttons `.btn` (+ `.btn-primary`, `.btn-danger`, `.btn-ghost`, `.btn-sm`), fields `.field` (stacked) / `.field-caps` (toolbar caps label) / `.check` (inline checkbox), surfaces `.panel`, `.toolbar`, `.callout-*`, `.chip-*`, `.empty-state`. Native inputs/selects/checkboxes are themed by zero-specificity defaults in `styles/forms.css`. Dialogs use `shared/chrome/Modal` / `ConfirmPopup` (never `window.confirm`). Top-level groups: `app/` (routing shell — `AppShell`, `PageHeader`), `shared/` (`api/`, `cache/`, `chrome/`, `dashboard-kit/`, `export/`, `gitops/`, `recommendations/`), `features/` (route domains: `status/`, `service/`, `logs/`, `deploy/`, `notifications/`, `alerts/`, `firewall/`, `rbac/`, `settings/`, `inbox/`, `events/`, `trends/` with `panel/`, `chart/`, `runtime/`, `range/`, `strategies/`), and `styles/`. SPA unit tests under `test/` mirror those folders; shared arrange helpers live in `test/fixtures.ts`.

### UI patterns

Every route should read the same way. Reach for these before writing page-local CSS:

| Need | Use |
|------|-----|
| Spacing / secondary type | `--space-1…6`, `--text-xs/sm/md`, `--radius-sm/control/panel` in `styles/tokens.css` |
| Page title + page-level actions | `PageHeader` `actions` (secondary `.btn`s first, one `.btn-primary` last). Don't put page CRUD inside a panel head. |
| Section-level controls (panel head, toolbars) | `.btn .btn-sm` |
| Row actions | `.btn-sm` text buttons in a `.btn-group`, or `.btn-icon` (+ `.is-danger`) with `aria-label` + `title` |
| Mutually exclusive mode switch | `.segmented` with `role="tablist"` + `aria-selected` |
| List of named entities with actions | `.item-list` > `.item-row` (`.item-row-main`, `.item-row-title`, `.item-row-meta`, `.item-row-actions`; `.is-disabled`) |
| Loading / failed load / empty | `shared/chrome/StateViews`: `LoadingState`, `ErrorState` (pass `onRetry`), `EmptyState` (title, guidance, optional CTA) |
| Unsaved draft (General, Firewall, RBAC) | sticky `SaveBar` as the only primary Save + `useUnsavedGuard` (header keeps Reload / mode) |
| Long pages | `.side-nav` sidebar inside `.with-aside` (Settings), or `.jump-nav` strip (Service); both use `useScrollSpy` + `jumpToSection` |
| Modal footer | `.modal-actions`: Cancel first, then `.btn-primary` (or `.btn-danger` for destructive confirms) |

Top-bar IA: primary nav is **Monitor** only (Status, Events). Settings live under the gear hub; on `/settings*` a sticky `SettingsSubNav` lists General / Alerts / Notifications / Firewall / RBAC (`SETTINGS_SECTIONS`). Account identity + logout sit under the user menu. Entries with a `permission` hide via `navAllowed` when RBAC denies it (`app/navItems.ts`).

## Develop

```bash
cd src/spa
npm ci
npm run dev # Vite on :5173; proxies /api → raft serve :8787
```

In another terminal: `raft serve` (or `uv run raft serve`). For editable installs, bake once so the packaged path has assets:

```bash
cd src/spa && npm ci && npm run build
```

## Ship FE changes

Change **`src/spa/` only**. Do **not** commit hashed files under `share/serve/spa/` (gitignored; `.gitkeep` keeps the directory).

Operators get the UI from the **Release wheel** (bake happens in the Release job). PR CI builds the SPA for tests; a failed bake/build on Release publish fails the release.

Local packaging / `raft serve` in a checkout still needs `npm run build` into the share path before you exercise the packaged UI.
