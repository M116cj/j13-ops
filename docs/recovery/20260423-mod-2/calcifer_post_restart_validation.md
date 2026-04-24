# Calcifer Post-Restart Validation — MOD-2 Phase 1b

**Order**: `/home/j13/claude-inbox/0-3` Phase 1 second output
**Executed**: 2026-04-23T03:55:22Z restart → T+60s verification
**Status**: **VERIFIED healthy, no behavioral drift.**

---

## 1. Validation checklist

| Check | Method | Result |
|---|---|---|
| Supervisor state | `systemctl is-active` | `active` |
| MainPID stable post-stabilization | `systemctl show -p MainPID` | 3574476 persisted through T+0 → T+60s |
| ActiveEnterTimestamp ≥ source mtime (§17.6) | epoch math | **FRESH** |
| Journal errors | `journalctl -u calcifer-supervisor --since "2 min ago"` | Only systemd lifecycle messages (Stopping/Stopped/Starting/Started). No ERROR, no Traceback. |
| Deploy-block logic still active | `/tmp/calcifer_deploy_block.json` mtime advanced post-restart | **YES** — +104s from pre-restart ts |
| RED state preserved | JSON `.status` field | **RED** (unchanged) |
| §17.3 threshold unchanged | JSON `.reason` contains `>6.0h` | **VERIFIED** |
| Atomic file write | `os.replace()` + tmp suffix (visible in code) | PASS — no partial-write visible |
| Persisted state file | `/home/j13/j13-ops/calcifer/deploy_block_state.json` | Written (matches zangetsu_outcome.py `_persist()` contract) |

## 2. Behavioral drift probes (look for anything unexpected after ae738e37 activation)

| Probe | Expected | Observed | Verdict |
|---|---|---|---|
| Telegram RED→GREEN transition alert | Only on status change; current run = RED, prior = RED | No Telegram emission | ✅ correct (no transition) |
| `zangetsu_status` VIEW reads | Pre-existing query pattern | Same query shape (verified from zangetsu_outcome.py source): `SELECT deployable_count, last_live_at_age_h FROM zangetsu_status` | ✅ |
| Block-file schema | Matches zangetsu_outcome.py authoring | `{status, deployable_count, last_live_at_age_h, ts, iso, reason}` | ✅ 1:1 |
| Extra modules fired | supervisor.py registers `check_zangetsu_outcome` tool + existing tools | No abnormal tool errors in journal | ✅ |
| `deploy_block_state.json` location | per zangetsu_outcome.py `DEPLOY_BLOCK_STATE` constant | `/home/j13/j13-ops/calcifer/deploy_block_state.json` (as coded) | ✅ |

## 3. Non-drift verification (things that must NOT have changed)

- Calcifer maintenance schedule (docker_prune / postgres_vacuum / redis_health / akasha_compact / log_rotation / backup_verify / disk_memory_gpu / zangetsu_status) — unchanged per existing cron
- Calcifer Telegram chat routing — unchanged
- Calcifer Gemma4 Ollama endpoint wiring — unchanged
- Worker supervision boundaries — supervisor does NOT control arena (arena still frozen)

## 4. Post-restart live-scan log

Block file mtime progression (VERIFIED observation):

| T+ | Block file mtime ISO | Interpretation |
|---|---|---|
| −104s | 2026-04-23T03:53:41Z | Last write by OLD supervisor pid 1807052 |
| 0s | restart issued | — |
| +3s | 2026-04-23T03:55:25Z | **First write by NEW supervisor pid 3574476** — proves ae738e37 active |

## 5. Q1 adversarial

| Dim | Finding | Verdict |
|---|---|---|
| Input boundary | VIEW returns well-formed row (deployable=0, age=NULL) → `_is_red()` correctly detects NULL→RED | PASS |
| Silent failure | If `_query_view()` had thrown, block file would NOT be rewritten; the +3s rewrite proves no silent fail | PASS |
| External dep | Docker postgres reachable (queryable from zangetsu_outcome 10s timeout) | PASS |
| Concurrency | Single supervisor process; atomic os.replace | PASS |
| Scope creep | Validation is read-only + restart; no config change | PASS |

## 6. Conclusions

- **VERIFIED**: ae738e37 is active runtime state
- **VERIFIED**: §17.3 deploy-block logic preserved
- **VERIFIED**: RED held (no cosmetic "unblock")
- **DISPROVEN**: any concern that the restart introduced behavioral drift

## 7. Exit condition

Calcifer formalization is LIVE. 0-3 Phase 1 success criterion 1 ("Calcifer formalization is live") — met.
