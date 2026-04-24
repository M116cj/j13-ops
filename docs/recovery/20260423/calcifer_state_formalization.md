# Calcifer State Formalization

**Order**: `/home/j13/claude-inbox/0-1` Phase C action 2
**Produced**: 2026-04-23T01:28Z
**Lead**: Claude
**Status**: **EXECUTED** — commit `ae738e37` on main
**Scope**: formalize the §17.3 outcome-watch code that was operating uncommitted in working tree, plus stop tracking runtime-state files that were polluting every commit diff.

---

## 1. Pre-commit working-tree state (VERIFIED at 2026-04-23T01:21Z)

```
modified:   calcifer/maintenance.log
modified:   calcifer/maintenance_last.json
modified:   calcifer/report_state.json
modified:   calcifer/supervisor.py

Untracked files:
  calcifer/deploy_block_state.json
  calcifer/zangetsu_outcome.py
```

## 2. Classification of each file (VERIFIED)

| File | Kind | Correct handling |
|---|---|---|
| `calcifer/supervisor.py` | CODE (tracked) | commit the diff |
| `calcifer/zangetsu_outcome.py` | CODE (untracked) | commit as new file |
| `calcifer/maintenance.log` | **RUNTIME STATE** (incorrectly tracked) | `git rm --cached` + gitignore |
| `calcifer/maintenance_last.json` | **RUNTIME STATE** (incorrectly tracked) | `git rm --cached` + gitignore |
| `calcifer/report_state.json` | **RUNTIME STATE** (incorrectly tracked) | `git rm --cached` + gitignore |
| `calcifer/deploy_block_state.json` | **RUNTIME STATE** (untracked) | gitignore only |

## 3. Code validity audit — `zangetsu_outcome.py`

Reviewed full file (130 lines). Classification: **VALID §17.3 outcome-watch implementation.**

### 3.1 Contract compliance

| §17.3 requirement | Implementation | Verdict |
|---|---|---|
| Poll `zangetsu_status` VIEW every 5 min | `_query_view()` + supervisor scheduler tick | ✅ |
| `deployable_count==0 AND last_live_at_age_h>6` → RED | `_is_red()` exactly matches threshold `AGE_RED_HOURS = 6.0`; `age_h is None` also → RED (first-start case, not in spec but safe) | ✅ (extends spec safely) |
| Write `/tmp/calcifer_deploy_block.json` when RED | `_persist()` atomic `tmp` + `os.replace()` | ✅ atomic |
| Clear flag when GREEN | `os.remove(DEPLOY_BLOCK_FLAG)` | ✅ |
| No LLM judgment in gate path | zero Ollama/LiteLLM calls in module | ✅ |
| Side-channel-deterministic | only subprocess to `docker exec psql` with 10s timeout | ✅ |

### 3.2 Q1 adversarial check on `zangetsu_outcome.py`

| Dim | Probe | Result |
|---|---|---|
| Input boundary | VIEW row malformed → `ValueError(f"malformed VIEW row: {line!r}")` returned as string, no crash | PASS |
| Silent failure | `_query_view` raises → caller returns `f"§17.3 ERROR: ..."` string (LLM sees error, flag not touched — keeps last state) | PASS |
| External dep | psql timeout=10s bounded; `tg_send` failure caught with `Exception` handler (line 124), returns `tg_failed` string instead of propagating | PASS |
| Concurrency | `os.replace()` is atomic on POSIX; two supervisor ticks can't corrupt flag | PASS |
| Scope creep | file is 130 lines, single responsibility (outcome gate); no side effects outside 2 files and Telegram callback | PASS |

### 3.3 Minor observations (not blockers)

- Uses bare `Exception` catch at line 124 (tg_send); acceptable for "do not break gate on Telegram failure" invariant, but a typed catch (`RequestException`) would be tighter. Deferred — not blocking.
- `DEPLOY_BLOCK_STATE = "/home/j13/j13-ops/calcifer/deploy_block_state.json"` — absolute path. Acceptable because Calcifer is a single-machine service; not portable but not intended to be.

## 4. Actions executed

### 4.1 Extended `.gitignore`

Appended (after existing `calcifer/calcifer.log` line):

```
# calcifer runtime state (added 2026-04-23 per Phase C formalization)
calcifer/maintenance.log
calcifer/maintenance_last.json
calcifer/report_state.json
calcifer/deploy_block_state.json
```

### 4.2 `git rm --cached` on three previously-tracked state files

```
rm 'calcifer/maintenance.log'
rm 'calcifer/maintenance_last.json'
rm 'calcifer/report_state.json'
```

History preserved (tags + old commits still contain them); HEAD forward no longer tracks.

### 4.3 Commit

```
commit ae738e37724b88d8a93205bac7ab360c4286ba4e (HEAD -> main)
fix(zangetsu/calcifer): formalize §17.3 outcome watch + ignore runtime state

 .gitignore                     |   6 ++
 calcifer/maintenance.log       |  80 -------------------------
 calcifer/maintenance_last.json |  47 ---------------
 calcifer/report_state.json     |   1 -
 calcifer/supervisor.py         |   3 +-
 calcifer/zangetsu_outcome.py   | 130 +++++++++++++++++++++++++++++++++++++++++
 6 files changed, 138 insertions(+), 129 deletions(-)
```

### 4.4 Verification (VERIFIED 2026-04-23T01:30Z)

```
$ git log -1 --format='%H %s'
ae738e37724b88d8a93205bac7ab360c4286ba4e fix(zangetsu/calcifer): formalize §17.3 outcome watch + ignore runtime state

$ git status --short
?? docs/
```

Remaining untracked = `docs/recovery/20260423/` directory (Phase A/B/C/D outputs, will be committed in a separate `docs(zangetsu/recovery-20260423)` commit after all Phase C/D/E docs land).

## 5. Why this is NOT a `feat(zangetsu/vN)` commit

§17.3 deploy block is RED (`deployable_count=0`). Per §17.3, `feat(zangetsu/vN)` commits are forbidden until deployable_count moves. This commit uses `fix(zangetsu/calcifer)` prefix — a maintenance/infra fix, not a version bump. Consistent with R2's use of `fix(zangetsu/r2-hotfix)` prefix (bd91face) during the same RED window.

## 6. Downstream consequences

### 6.1 Working-tree cleanliness
Supervisor scheduler will continue writing to `maintenance.log`, `maintenance_last.json`, `report_state.json`, `deploy_block_state.json` as it runs. These files will no longer appear in `git status` and will not pollute any future commit diff.

### 6.2 Calcifer service restart
`calcifer-supervisor.service` is currently running against the pre-commit supervisor.py binary (ExecStart reads from disk on each start). The new tool `check_zangetsu_outcome` will NOT be picked up until next restart. Per §17.6, a restart must have `proc start > source mtime`. Restart command:

```bash
sudo systemctl restart calcifer-supervisor.service
# verify FRESH:
PROC=$(systemctl show calcifer-supervisor -p ActiveEnterTimestamp --value | xargs -I{} date -d {} +%s)
SRC=$(stat -c %Y /home/j13/j13-ops/calcifer/supervisor.py)
[ "$PROC" -gt "$SRC" ] && echo FRESH || echo STALE
```

**NOT EXECUTED in this Phase C formalization** — awaiting j13 sudo approval (sudo required for `systemctl restart` on system units). Deferred task flagged in `infra_blocker_report.md` §4.

### 6.3 No visible state change
`/tmp/calcifer_deploy_block.json` content unchanged (Calcifer still writing via the old supervisor path + its existing `check_zangetsu_outcome` not-yet-registered tool). Post-restart, behaviour is functionally identical because the NEW `zangetsu_outcome.py` matches §17.3 spec and the PRE-existing RED block file was already being maintained by an ad-hoc path. This commit *replaces an ad-hoc path with a reviewed path* without changing observable behaviour.

## 7. Gap flagged (not fixed in this commit — separate tracks)

### 7.1 `/home/j13/calcifer-miniapp/` — NOT in git
38 KB `server.py` + `server.py.bak_v03_20260419_003612` + `calcifer-miniapp.service` + `.env` symlink. Zero version control. History only in server.py.bak filename convention.

Risk: rm -rf or disk failure = irrecoverable.

Recommendation: create `M116cj/calcifer-miniapp` GitHub repo, `git init` local, push initial state. NOT done here — needs j13 decision on org / repo name / visibility. Flagged in `infra_blocker_report.md` §3.

### 7.2 `/home/j13/d-mail-miniapp/` — NOT in git
Per Phase C local-only audit: also `fatal: not a git repository`. 1047-line `server.py` per AKASHA v0.5.5 record. Higher risk because d-mail-miniapp is the **primary command center** for @macmini13bot (all Claude Command Center traffic).

Recommendation: highest priority to formalize. Same flag in `infra_blocker_report.md` §3.

## 8. Non-negotiable rules compliance

| 0-1 rule | Evidence in this commit |
|---|---|
| 1. No silent production mutation | Commit message + this ADR + 6-file staged diff visible |
| 2. No silent threshold change | §17.3 AGE_RED_HOURS=6.0 unchanged |
| 3. No silent gate change | same |
| 6. No mixed patches | calcifer only; does not touch zangetsu/, engine/, services/ |
| 8. No performance claims without evidence | commit claims "atomic write" — verified in code via `os.replace()` (POSIX atomic) |
| 9. No black-box | all 3 tool calls + Telegram callback explicit in code |
| 10. Labels applied | §3 Verdict column, §6 VERIFIED annotations |

## 9. Q1 for this formalization

| Dim | Verdict |
|---|---|
| Input boundary | PASS — classifies all 6 files by kind before action |
| Silent failure | PASS — `git rm --cached` is non-destructive (history preserved, HEAD tree only) |
| External dep | PASS — no network calls during commit; only local git + filesystem |
| Concurrency | PASS — commit is atomic git operation; supervisor.service still runs old binary until explicit restart |
| Scope creep | PASS — no code changes beyond 1 import + 1 tool registration + 130-line new file (all pre-written by earlier session, reviewed not modified) |
