# calcifer-miniapp Repo Init Report — MOD-2 Phase 2

**Repo**: `github.com/M116cj/calcifer-miniapp` (private)
**Initial commit**: `1c221328d494d05b02f4616b4ab0b7971d0753ea`
**Executed**: 2026-04-23T03:58Z

---

## 1. Why now

Prior state: 38 KB `server.py` serving diagnostic-fallback UI on port 8772. Superseded in production by d-mail-miniapp v0.5.5 (which absorbed the full Ops stack 2026-04-18) but kept running as rollback reference. Zero VCS coverage. Single `.bak_v03_20260419_003612` as filename-suffix "history".

Severity in `architecture_drift_map.md §MOD-1.B (D-24)`: **CRITICAL** (paired with d-mail-miniapp).

## 2. Steps executed

1. `cd /home/j13/calcifer-miniapp`
2. Wrote `.gitignore` (31 entries)
3. Wrote `README.md` (28 lines — documents supersession by d-mail-miniapp v0.5.5, kept as diagnostic fallback)
4. `git init -b main` + `git add -A`
5. `gh repo create M116cj/calcifer-miniapp --private --description "Calcifer Ops MiniApp (diagnostic fallback, superseded by d-mail-miniapp v0.5.5) — port 8772"`
6. `git commit` (initial, 7 files, 2155 insertions)
7. `git remote add origin https://github.com/M116cj/calcifer-miniapp.git`
8. `git push -u origin main` — success
9. `gh repo view --json` — confirmed private + main default

## 3. Files committed

```
.gitignore               |   31 +
README.md                |   28 +
calcifer-miniapp.service |   16 +
deploy.sh                |   21 +
requirements.txt         |    4 +
server.py                | 1035 +
static/index.html        | 1020 +
```

## 4. Files deliberately excluded

| File | Rationale |
|---|---|
| `.env` (symlink → `/home/j13/alaya/calcifer/.env`) | Target lives outside repo scope; symlink itself not tracked |
| `.venv/` | Build artifact |
| `__pycache__/`, `.pyc` (49 KB) | Python bytecode |
| `server.py.bak_v03_20260419_003612` (12 KB) | Older version, deprecated by git |
| `static/index.html.bak_v03_20260419_003612` (18 KB) | Older frontend |

## 5. Secret leak audit

```bash
$ git diff --cached | grep secret-patterns
# (results: only `BOT_TOKEN = os.environ.get("CALCIFER_TG_TOKEN", "")` env-reference; no values)
```

No raw token values in commit. `.env` is symlinked outside repo.

## 6. Post-push verification

```
{"defaultBranchRef":{"name":"main"},"name":"calcifer-miniapp","url":"https://github.com/M116cj/calcifer-miniapp","visibility":"PRIVATE"}
```

## 7. Impact on runtime

**ZERO runtime impact.** Service still running from `/home/j13/calcifer-miniapp/server.py` via systemd. Only VCS state is new.

## 8. Role in architecture post-MOD-2

Per `README.md` and `modular_target_architecture.md`, calcifer-miniapp is a **diagnostic-fallback UI**, NOT the primary command center. Primary UX is `/dmail/` port 8771 (d-mail-miniapp). calcifer-miniapp remains as:
- Rollback-safe reference implementation (pre-v0.5.5 Ops merge)
- Diagnostic read surface if d-mail-miniapp is unavailable

## 9. Drift delta

- B4 (infra blocker) — RESOLVED
- D-24 (architecture drift; paired with d-mail) — CRITICAL → RESOLVED

Gate-A.1 prerequisite "off-VCS miniapp risk removed" for this miniapp: **MET.**
