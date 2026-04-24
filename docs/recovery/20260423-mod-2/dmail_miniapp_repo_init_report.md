# d-mail-miniapp Repo Init Report — MOD-2 Phase 2

**Repo**: `github.com/M116cj/d-mail-miniapp` (private)
**Initial commit**: `4fea30c2b0659d29ad57adb14b06b32864bca78f`
**Executed**: 2026-04-23T03:58Z

---

## 1. Why now (evidence)

Prior state: 1047-line FastAPI service hosting primary Claude Command Center UX for j13. Zero VCS coverage. Filename-suffix "history" (5× `server.py.bak_*` + 7× `index.html.bak_*`). Blast radius: single disk failure = full rebuild with no review trail.

Severity classification in `docs/recovery/20260423-mod-1/architecture_drift_map.md §MOD-1.B (D-24)`: **CRITICAL**.

## 2. Steps executed

1. `cd /home/j13/d-mail-miniapp` (existing service dir on Alaya)
2. Wrote `.gitignore` (34 entries covering secrets / venv / cache / timestamped backups / IDE / runtime)
3. `sudo cp /etc/systemd/system/d-mail-miniapp.service ./d-mail-miniapp.service.unit` + `chown j13:j13` (copy for deploy reference)
4. Wrote `README.md` (40 lines — architecture, 15 endpoints summary, deployment runbook)
5. `git init -b main` + `git add -A`
6. `gh repo create M116cj/d-mail-miniapp --private --description "Claude Command Center — @macmini13bot Telegram MiniApp (port 8771, self-contained systemd)"`
7. `git commit` (initial commit, 6 files, 3131 insertions)
8. `git remote add origin https://github.com/M116cj/d-mail-miniapp.git`
9. `git push -u origin main` — success
10. `gh repo view --json` — confirmed private + main default

## 3. Files committed (exact)

```
.gitignore                  |   34 +
README.md                   |   40 +
d-mail-miniapp.service.unit |   24 +
requirements.txt            |    4 +
server.py                   | 1244 +
static/index.html           | 1785 +
```

## 4. Files deliberately excluded (with rationale)

| File/pattern | Reason for exclusion |
|---|---|
| `.env` (150 B) | Contains live `TELEGRAM_BOT_TOKEN=8739079697:...` + `CLAUDE_INBOX_TOKEN=133d95...` — secrets MUST stay on host |
| `.venv/` | Build artifact, 100s of MB; recreatable via `pip install -r requirements.txt` |
| `__pycache__/` (59 KB .pyc) | Python bytecode; recreatable |
| `server.py.bak_pre_output_fix_20260421_022233` (46 KB) | Pre-v0.5.5 backup; deprecated by git from now on |
| `server.py.bak_v057_20260419_085042` (38 KB) | Older version |
| `server.py.bak_v058_20260419_102935` (38 KB) | Older version |
| `server.py.pre_team_scope_20260419` (41 KB) | Older version |
| 7× `static/index.html.bak_*` + `pre_*` (15 KB–60 KB) | Frontend backups |

Future sessions: if any historical `.bak` body is needed, retrieve from Alaya host (`/home/j13/d-mail-miniapp/server.py.bak_*`) OR from git reflog if it was staged prior. They were never staged in this initial commit — confirmed by `git diff --cached --stat`.

## 5. Secret leak audit

```bash
$ git diff --cached | grep -iE "TELEGRAM_BOT_TOKEN|CLAUDE_INBOX_TOKEN|^(\+)[A-Z_]+=[A-Za-z0-9:_-]{20,}"
# (results: only code references like `os.environ.get("TELEGRAM_BOT_TOKEN", "")`; no actual values)
```
No raw token values present in commit tree. GitHub secret scanning recommended as post-push safety net.

## 6. Post-push verification

```
{"defaultBranchRef":{"name":"main"},"name":"d-mail-miniapp","url":"https://github.com/M116cj/d-mail-miniapp","visibility":"PRIVATE"}
```

## 7. Impact on runtime

**ZERO runtime impact.** Service still runs from `/home/j13/d-mail-miniapp/server.py` via systemd. Only VCS state is new. `.gitignore` does not affect service behavior.

## 8. Drift delta

- B3 (infra blocker) — RESOLVED
- D-24 (architecture drift) — CRITICAL → RESOLVED

Gate-A.1 prerequisite "off-VCS miniapp risk removed" for this miniapp: **MET.**
