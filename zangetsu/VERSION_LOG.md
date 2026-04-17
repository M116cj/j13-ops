# zangetsu — VERSION LOG

> Per `_global/feedback_project_naming.md`: bare project folder name + this log file as single-source-of-truth for "what changed when".
> Latest version on top. Per-feature granularity required.

---

## v0.2.0 — 2026-04-17 — Folder rename: `zangetsu_v5` → `zangetsu`
**Engine hash:** `zv5_v71` (unchanged — runtime stamp axis decoupled from folder)
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: project folder rename
- **Change type:** refactor (physical layout)
- **What changed:**
  - `~/j13-ops/zangetsu_v5/` → `~/j13-ops/zangetsu/` (git mv, history preserved)
  - 43 code/config files swept: all `zangetsu_v5` → `zangetsu` in imports / paths / SQL DSN / shell scripts
  - 10 systemd unit files updated (`/etc/systemd/system/{arena,console,dashboard,calcifer,health-monitor,live-trader}*.service`)
  - 2 cron entries updated (watchdog + daily_data_collect)
  - 46 `.venv/bin/` script shebangs sed-rewritten
  - Lock dir `/tmp/zangetsu_v5/` → `/tmp/zangetsu/`
  - Mac scan script `~/.claude/scratch/v32-deep-scan.sh` updated
- **Why:** Adopting new project naming rule (`feedback_project_naming.md`). Version-suffixed dirs caused the V9 全局修復 saga: scan tooling stayed at V3 paths, schemas, modules — silent decay. Folder names should be physical-layer identifiers; doctrine version (V9 Sharpe Quant) lives in code/branch, runtime version (`zv5_v71`) lives in DB.
- **Q1/Q2/Q3:** PASS — 6 workers restarted clean, all imports green, systemd 3 conflict units stay disabled, no inflight-data loss (workers idle at rename moment)
- **Rollback:** `git mv zangetsu zangetsu_v5 && sudo find /etc/systemd/system -name "*.service" -exec sed -i "s|zangetsu/|zangetsu_v5/|g" {} \; && sudo systemctl daemon-reload && crontab /tmp/zangetsu-crontab.bak && bash zangetsu_ctl.sh restart`

### Non-feature changes
- `engine_hash` in DB stays `zv5_v71` — intentional decoupling per project_naming feedback rule
- `zangetsu_ctl.sh` still echoes "Zangetsu V5 services" string in startup banner — cosmetic, acceptable; will rename to "V9" when next version logical

---

## v0.1.1 — 2026-04-17 — Pidlock import-time fix + scan rewrite + pytest config
**Engine hash:** `zv5_v71`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `bb1602fc`

### Feature: pidlock single-instance guard
- **Change type:** fix
- **What changed:** moved `acquire_lock()` from module top-level into `if __name__ == "__main__"` guard in 4 services: `arena_pipeline.py`, `arena13_feedback.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`
- **Why:** any `import` of these services triggered pidlock → `sys.exit(1)`, breaking scan/test/lint pipelines silently. V3.2 scan reported "S01 import failure" with empty error → this was the root cause.
- **Q1/Q2/Q3:** PASS — commit `3dc1304e`
- **Rollback:** `cp services/{name}.py.bak2 services/{name}.py`

### Feature: pytest async test support
- **Change type:** new
- **What changed:** added `zangetsu/pytest.ini` with `asyncio_mode = auto`; installed `pytest-asyncio` 1.3.0 in `.venv`
- **Why:** 3 integration tests were silently skipped because pytest didn't recognize `async def`. After fix, 1 test now passes; 2 still fail on asyncpg credentials (separate test-infra issue, not in scope here).
- **Q1/Q2/Q3:** PASS — commit `bb1602fc`
- **Rollback:** `rm pytest.ini && pip uninstall pytest-asyncio`

### Feature: V3.2 scan script rewrite (Mac side)
- **Change type:** refactor
- **What changed:** `~/.claude/scratch/v32-deep-scan.sh` rewritten from V3 era to V9 reality:
  - Paths: `zangetsu_v3` → `zangetsu_v5` (later → `zangetsu` in v0.2.0)
  - SQL: V3 tables (`factor_candidates` etc.) → V9 schema (`champion_pipeline`, `pipeline_state`, `pipeline_errors` with correct column names)
  - Module check list: V9 module layout
  - S01 stderr handling fixed (was treating optional-lib WARNINGs as failures)
  - ps grep aligned to script-style invocation `services/(arena|v9_)`
  - Calcifer freshness JSON parse guarded
  - New section: Service Manager Conflict Check (auto-detects systemd-vs-ctl issues)
- **Why:** Old script was V3-era; reported false MISSING for everything V9 had refactored. Couldn't distinguish "broken" from "intentionally moved."
- **Q1/Q2/Q3:** PASS — minimal changes per section, verified by re-running scan
- **Rollback:** `cp v32-deep-scan.sh.v3.bak v32-deep-scan.sh` (kept on Mac /tmp)

### Feature: redundant systemd units disabled
- **Change type:** infra cleanup
- **What changed:** `systemctl stop && disable` for `arena-pipeline`, `arena23-orchestrator`, `arena45-orchestrator`, `arena13-feedback`, `arena13-evolution`, `arena13-feedback.timer`. Workers continue running via `zangetsu_ctl.sh + watchdog.sh` (manual `&` spawn model — confirmed by reading `watchdog.sh` restart logic).
- **Why:** Systemd units were spawning workers in restart loop, losing pidlock to ctl.sh-spawned ones. Pure log noise. Watchdog uses `LOCK_TO_SYSTEMD` map but its actual restart path uses `eval $cmd > log 2>&1 &` (not `systemctl restart`) — so systemd units were never the real management.
- **Q1/Q2/Q3:** PASS — V9 scan went from `⚠️ Systemd units in failure/restart loop` to `✅ Systemd units stable`
- **Rollback:** `sudo systemctl enable && start arena-pipeline arena23-orchestrator arena45-orchestrator`
