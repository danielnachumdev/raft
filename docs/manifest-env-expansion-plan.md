# App manifest env expansion — implementation plan

Single source of truth for letting **one** committed App manifest serve **Dev and Prod** (and other stages) by expanding **`${VAR}`** placeholders when the manifest is **applied**.

**Consumer:** LimudPsanter raft CD ([frontend `docs/raft-deploy-plan.md`](https://github.com/DanielMusicIL/danielmusicil-limudpsanter-frontend/blob/HEAD/docs/raft-deploy-plan.md)) — PR→Dev / merge→Prod; distinct App identity per stage; CI exports stage vars then `raft apply --file`.

**Do not invent alternate field names mid-flight;** edit this file first.

---

## Roles (Who)

| Who | Means |
|-----|--------|
| **Me** | Coding agent in this raft checkout |
| **You** | Review plan locks, PRs, VPS upgrade Sanity |

---

## Goals

1. Operators (and CI) can keep **one** `.raft/app.yaml` with placeholders for stage-specific fields (`metadata.name`, `spec.group`, `publicHost`, `envFile`, `path`, `ref`, …).
2. Expansion happens **inside raft** at **`apply`** (file and git), from a clear env source — no Jinja, no second manifest dialect.
3. Applied registry state under `~/.raft/state/apps/` stores the **expanded** document (concrete YAML) so later `render` / `redeploy` / `doctor` do **not** re-expand with a different environment.
4. Fail closed on missing variables (no silent empty hosts/names).
5. **100% unit coverage** remains (`--cov-fail-under=100`).

---

## Non-goals

- Templating **`~/.raft/settings.yaml`**, Compose files, or nginx configs.
- Expanding **container** `spec.envFile` / `spec.env` **file contents** (Docker already loads those).
- Full template languages (Jinja, Go templates, conditionals, loops).
- Changing registry keying (still `metadata.name` after expansion) — callers must supply distinct names for concurrent Apps.
- Requiring CI to pre-`envsubst` (CI **may** still do that; raft expansion is the product path).

---

## Locked design

### Syntax

| Form | Meaning |
|------|---------|
| `${NAME}` | Required: value from apply env; error if unset or empty |
| `${NAME:-default}` | If unset or empty, use `default` (may be empty string only if default is explicitly empty — **v1: disallow empty default** for safety, or allow; **lock: allow empty default**) |
| `$${` | Escape → literal `${` |

- Names: `[A-Za-z_][A-Za-z0-9_]*` (shell-like).
- Expansion runs on the **raw file text** **before** `yaml.safe_load` (same mental model as `envsubst`).
- No expansion inside unescaped content that is not `${…}` / `$${`.

### Variable sources (merge order, later wins)

1. Process environment (`os.environ`) when `raft apply` runs.
2. Optional **`--env-file PATH`** on `raft apply` (dotenv-style `KEY=VALUE` lines; `#` comments; no export required). Later keys in the file override earlier; file overrides process for the same key.
3. Optional repeatable **`--env KEY=VALUE`** on `raft apply` (highest precedence) for CI one-offs.

Documented env prefix for examples: consumers may use `RAFT_APP_*` but raft does **not** require a prefix.

### Where it runs

| Entry | Expands? |
|-------|----------|
| `raft apply --file PATH` | Yes, after read, before parse |
| `raft apply --git …` | Yes, when reading the cloned `.raft/app.yaml` |
| Reading `~/.raft/state/apps/*.yaml` for render/redeploy/doctor | **No** (already expanded at apply) |
| `raft sync` / image pin only | N/A |

### Registry write

`write_registry_app` persists the **parsed object built from expanded YAML** (same as today after load) — operators inspecting state see concrete hosts/names, not placeholders.

### Errors (operator-facing)

```text
manifest at PATH: undefined variable FOO in ${FOO}
Fix: export FOO=… or pass --env-file / --env FOO=…
```

```text
manifest at PATH: invalid placeholder near …
Fix: use ${NAME}, ${NAME:-default}, or $${ for a literal ${
```

### Example (consumer-shaped)

```yaml
apiVersion: raft/v1
kind: App
metadata:
  name: ${RAFT_APP_NAME}

spec:
  group: ${RAFT_APP_GROUP}
  www: false
  publicHost: ${RAFT_APP_PUBLIC_HOST:-}
  tls: origin

  source: docker
  image: ghcr.io/danielmusicil/limudpsanter-frontend
  ref: ${RAFT_APP_REF}
  path: ${RAFT_APP_PATH}

  dependsOn:
    - ${RAFT_APP_DEPENDS_ON_BACKEND}

  envFile: ${RAFT_APP_ENV_FILE}

  ports:
    - name: http
      containerPort: 80
      expose: http
```

CI Dev:

```bash
export RAFT_APP_NAME=frontend-dev
export RAFT_APP_GROUP=limudpsanter-dev
export RAFT_APP_PUBLIC_HOST=dev.limudpsanter.co.il
# …
raft apply --file .raft/app.yaml --no-deploy
```

Backend with no public host: omit `publicHost` or use a template without that key for internal Apps (prefer **two small templates** only if YAML structure diverges; same expansion engine).

---

## CLI surface

```text
raft apply --file PATH [--env-file PATH] [--env KEY=VALUE]... [--ref REF] [--no-deploy]
raft apply --git URL [--ref REF] [--env-file PATH] [--env KEY=VALUE]... [--no-deploy]
```

- `--env-file` / `--env` apply only to **manifest expansion**, not to Compose service environment.
- Help text must spell that distinction (avoid confusion with `spec.envFile`).

Fire/argparse: wire through `cli/root.py` → `AppApply.apply_file` / `apply_git`.

---

## Implementation steps

### Step 0 — Lock

**Who:** You

Confirm:

1. Text expansion before YAML parse (not post-parse string walk).
2. Fail if `${NAME}` unset/empty; `${NAME:-default}` allowed.
3. Registry stores expanded YAML only.
4. `--env-file` / `--env` on apply only.

---

### Step 1 — Pure expander module + unit tests

**Who:** Me

- New helper e.g. `raft.services.manifest_env.expand_manifest_text(text, env: Mapping[str, str]) -> str`
- Parse dotenv file helper for `--env-file`
- Tests: required, default, escape, missing, invalid name, nested-looking strings, YAML remains valid after expand

```bash
uv run pytest tests/unit/ -q -k manifest_env
```

---

### Step 2 — Wire `apply_file` / `apply_git`

**Who:** Me

- Build env map: `os.environ` → file → `--env`
- Expand `raw` before `yaml.safe_load`
- Preserve existing `ref_override` behavior **after** load (unchanged)

Tests: apply with temp manifest containing `${…}`; assert registry file has concrete values; missing var → `OperatorError`.

---

### Step 3 — CLI flags + help

**Who:** Me

- `--env-file`, repeatable `--env`
- AGENTS.md + README short blurb + example under `examples/` (e.g. extend an existing example with one placeholder + comment)

---

### Step 4 — Coverage gate

**Who:** Me

```bash
uv run pytest tests/unit --cov=raft --cov-fail-under=100
```

---

### Step 5 — Ship + VPS

**Who:** You merge · Me notes · VPS `raft update` (or editable install)

#### Sanity

```bash
# on VPS as raft
export RAFT_APP_NAME=expand-smoke
# minimal manifest with ${RAFT_APP_NAME}
raft apply --file /tmp/smoke-app.yaml --no-deploy
raft get apps   # shows expand-smoke
# cleanup
raft delete app expand-smoke   # or equivalent existing delete path
```

LimudPsanter CI can then drop pre-`envsubst` once raft on the VM is upgraded (optional follow-up in consumer repos).

---

## Rollback

| Stage | Action |
|-------|--------|
| Before merge | Abandon branch |
| After merge, unused | Old manifests without `${` unchanged |
| After consumer templates | Pin previous raft; CI falls back to rendering concrete YAML before apply |

---

## Risks / notes

1. **Name collision** — Expansion does not fix Dev/Prod both expanding to `metadata.name: frontend`. Consumer plan must use distinct names.
2. **Secrets in `--env`** — Prefer `--env-file` mode 600 on the runner/VM; do not log expanded manifests at info level.
3. **Git apply + secrets** — Vars still come from the **apply process env**, not from the git repo.
4. **Default empty publicHost** — Internal Apps should omit the key or use a backend-specific template; expanding to empty string then failing schema is OK if parse rejects empty `publicHost` when `expose: http`.

---

## Progress log

| When | Note |
|------|------|
| 2026-09-23 | Plan drafted for LimudPsanter stage-aware CD (PR=Dev / main=Prod). Awaiting Step 0 lock. |
| 2026-09-23 | Step 0 locked by operator. Steps 1–4 implemented: `manifest_env` expander + dotenv, wired into `apply_file`/`apply_git` + CLI `--env-file`/`--env`, docs/help/example comment, unit coverage gate. Step 5 (VPS Sanity) deferred to operator. |
