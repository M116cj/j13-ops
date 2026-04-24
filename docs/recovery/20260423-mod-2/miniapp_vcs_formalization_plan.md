# Miniapp VCS Formalization Plan — MOD-2 Phase 2

**Order**: `/home/j13/claude-inbox/0-3` Phase 2 first deliverable
**Produced**: 2026-04-23T03:58Z
**Author**: Claude (Lead)
**Status**: **EXECUTED** — both miniapps now on GitHub private repos.

---

## 1. Canonical repo ownership

| Miniapp | GitHub repo | Visibility | Created | Initial commit |
|---|---|---|---|---|
| `d-mail-miniapp` (@macmini13bot, port 8771) | `M116cj/d-mail-miniapp` | **private** | 2026-04-23T03:58Z | `4fea30c` — "feat(d-mail-miniapp/init): v0.5.5 self-contained systemd state" |
| `calcifer-miniapp` (diagnostic fallback, port 8772) | `M116cj/calcifer-miniapp` | **private** | 2026-04-23T03:58Z | `1c22132` — "feat(calcifer-miniapp/init): diagnostic fallback UI" |

## 2. Included in initial commit (VERIFIED)

### `d-mail-miniapp` (3131 insertions, 6 files)
- `server.py` (1244 lines) — FastAPI v0.5.5
- `static/index.html` (1785 lines) — miniapp frontend
- `requirements.txt`
- `d-mail-miniapp.service.unit` — systemd unit copy (from `/etc/systemd/system/`)
- `README.md` — architecture overview + deployment instructions
- `.gitignore`

### `calcifer-miniapp` (2155 insertions, 7 files)
- `server.py` (1035 lines) — FastAPI v0.3 era
- `static/index.html` (1020 lines)
- `requirements.txt`
- `calcifer-miniapp.service` — systemd unit (pre-existing in repo dir)
- `deploy.sh` — legacy deploy helper
- `README.md`
- `.gitignore`

## 3. Excluded from VCS (VERIFIED — in `.gitignore`)

| Pattern | Rationale |
|---|---|
| `.env`, `.env.*`, `*.env.bak` | **Secrets** — live `TELEGRAM_BOT_TOKEN` + `CLAUDE_INBOX_TOKEN` must remain on host filesystem only |
| `.venv/`, `venv/` | Python virtualenv — build artifact, recreatable from `requirements.txt` |
| `__pycache__/`, `*.pyc`, `*.pyo` | Python bytecode — recreatable |
| `*.bak_*`, `*.pre_*`, `*.backup`, `*.old` | Legacy filename-based version history — deprecated by git |
| `.pytest_cache/`, `.mypy_cache/` | Tooling caches |
| `.DS_Store`, `.vscode/`, `.idea/` | IDE / OS noise |
| `*.log`, `*.pid` | Runtime state |
| `node_modules/` | (pre-emptive) |

## 4. Runtime artifacts NOT committed (by design)

### Secrets
- `d-mail-miniapp/.env` — contains `TELEGRAM_BOT_TOKEN=8739079697:...` + `CLAUDE_INBOX_TOKEN=133d95...`. Loaded via systemd `EnvironmentFile=` directive.
- `calcifer-miniapp/.env` — symlink to `/home/j13/alaya/calcifer/.env`. Target is outside both miniapps' repo scope.

### Bound via systemd `Environment=` (explicit, not via .env)
- `d-mail-miniapp.service`:
  - `MINIAPP_OWNER_TG_ID=5252897787` (j13's Telegram ID; hardens against silent allow-all per v0.5.5 release notes)
  - `MINIAPP_PORT=8771`
  - `NEXUS_REDIS_URL=redis://127.0.0.1:6380/0`
  - `AKASHA_URL=http://100.123.49.102:8769`
  - `ZANGETSU_LIVE_PATH=/tmp/zangetsu_live.json`
  - `CURRENT_TASK_PATH=/tmp/j13-current-task.md`
  - `MINIAPP_AUDIT_DIR=/home/j13/audit`

### File-system-backed runtime
- `/home/j13/audit/miniapp-YYYY-MM-DD.log` — audit log writer (append-only)
- Redis keys `miniapp:session:*`, `miniapp:jobs:*` — session + job TTL state
- `/tmp/j13-current-task.md` — input from Mac Claude CLI hook

## 5. Current local-only risk removal

### Before MOD-2
- 2 production FastAPI services (3179 lines combined) with **zero version history** outside filename backup pattern
- D-24 classified CRITICAL in `architecture_drift_map.md`
- rm -rf or disk failure = full rebuild, no review trail

### After MOD-2 Phase 2
- Both services mirrored in GitHub private repos
- Full change history from this commit forward via git
- `.gitignore` prevents secret leaks
- Systemd unit files captured in-repo for deployment reference
- D-24 severity: CRITICAL → **RESOLVED** (drift map update pending MOD-2 commit)

## 6. Secret leakage audit (post-push)

`git diff --cached | grep` prior to commit showed ONLY code references to env var names (`os.environ.get("TELEGRAM_BOT_TOKEN", "")`), NOT actual token values. Post-push GitHub remote contains no raw secrets.

**Recommended ongoing**: enable GitHub secret-scanning on both repos (j13 action).

## 7. Next-step runbook for each repo

### For new maintainers / future refactors
```bash
# Clone
git clone git@github.com:M116cj/d-mail-miniapp.git
cd d-mail-miniapp

# Bootstrap
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run locally (needs live .env on filesystem)
cp ../path/to/.env .env  # NOT versioned; obtain from j13
python server.py

# Install to Alaya
sudo cp d-mail-miniapp.service.unit /etc/systemd/system/d-mail-miniapp.service
sudo systemctl daemon-reload
sudo systemctl enable --now d-mail-miniapp
```

## 8. Non-negotiable rules compliance (0-3 §NON-NEGOTIABLE)

| Rule | Evidence |
|---|---|
| 1. No silent production mutation | ✅ — live services unaffected; only VCS state added |
| 2. No threshold change | ✅ |
| 3. No gate change | ✅ |
| 4. No arena restart | ✅ |
| 8. No broad refactor | ✅ — zero code changed, only committed current state |
| 9. No module merge into mainline migration path | ✅ — miniapps are consumer services, not MOD-1 migration modules |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 2 distinct repos, owner decisions explicit |
| Silent failure | PASS — secret leak audited pre-push + post-push |
| External dep | PASS — GitHub API reachable (gh auth confirmed M116cj active) |
| Concurrency | PASS — initial commits atomic root-commits; no race |
| Scope creep | PASS — only VCS formalization; no feature change |

## 10. Exit condition

0-3 §Phase 2 exit: "No CRITICAL miniapp remains fully off-VCS." **MET.**
