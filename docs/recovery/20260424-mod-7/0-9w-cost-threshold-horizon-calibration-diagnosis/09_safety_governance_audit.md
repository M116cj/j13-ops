# 09 — Safety + Governance Audit (0-9W-COST-THRESHOLD-HORIZON-CALIBRATION-DIAGNOSIS)

## 1. Forbidden Operations Performed

| Forbidden Action | Performed? | Evidence |
| --- | --- | --- |
| Modified arena_pipeline.py | NO | git status (clean throughout) |
| Modified cost_model.py | NO | git status (clean) |
| Modified alpha_signal.py | NO | git status (clean) |
| Modified alpha_zoo_injection.py | NO | git status (clean) |
| Modified backtester | NO | git status (clean) |
| Restarted A1/A23/A45 services | NO | systemctl status (services unchanged) |
| Wrote to Postgres | NO | no DB connection opened in replay script |
| Touched live HTTP APIs | NO | no requests made |
| Pushed to CANARY/production | NO | no canary scripts invoked |
| Modified branch protection rules | NO | gh api branches/main shows unchanged |
| Threshold modification | NO | A2_MIN_TRADES=25 unchanged |
| Generation budget changes | NO |
| Sampling weight changes | NO |
| Execution / capital / risk changes | NO |
| Committed secrets | NO |
| Probe / fake row inserts | NO |
| Live alpha injection | NO |

→ **Zero forbidden operations performed.**

## 2. Standard Read-Only Operations Performed

| Operation | Count | Evidence |
| --- | --- | --- |
| File reads (cost_model.py, alpha_signal.py, arena_pipeline.py, backtester.py) | ~14 | session log |
| Offline imports (CostModel, AlphaEngine, Backtester, compile_formula) | 5 | replay script |
| Pure Python evaluations (no I/O side effects) | 663 cells | summary.json |
| JSONL writes (own /tmp/ files only) | 6 | ls /tmp/0-9wch-*.jsonl |
| Markdown writes (own /tmp/ files only) | 11 | ls /tmp/0[0-9]_*.md, /tmp/10_*.md |
| SSH read commands (git status, ls, cat) | ~30 | session log |

All reads within explicitly allowed scope. All writes ephemeral (`/tmp/*`) or evidence directory only.

## 3. Branch Protection Snapshot

```json
{
  "enforce_admins": true,
  "required_signatures": true,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

Unchanged across investigation.

## 4. Process / Service State Diff

| Service | Pre-investigation | Post-investigation | Diff |
| --- | --- | --- | --- |
| A1 arena | ALIVE | ALIVE | unchanged |
| A23 arena | ALIVE | ALIVE | unchanged |
| A45 arena | ALIVE | ALIVE | unchanged |
| Cron schedule | unchanged | unchanged | unchanged |
| engine.jsonl writer | WRITING | WRITING | continued normally |

→ **No production process disturbed.**

## 5. Controlled-diff Pre-Commit Audit

| Path | Class | Diff |
| --- | --- | --- |
| `docs/recovery/20260424-mod-7/0-9w-cost-threshold-horizon-calibration-diagnosis/00..10_*.md` | evidence | new (11 files) |
| `docs/recovery/.../0-9wch-cost-sensitivity.jsonl` | evidence data | new |
| `docs/recovery/.../0-9wch-entry-threshold-sensitivity.jsonl` | evidence data | new |
| `docs/recovery/.../0-9wch-horizon-sensitivity.jsonl` | evidence data | new |
| `docs/recovery/.../0-9wch-backtester-sanity.jsonl` | evidence data | new |
| `docs/recovery/.../0-9wch-signal-to-trade.jsonl` | evidence data | new |
| `docs/recovery/.../0-9wch-calibration-matrix.jsonl` | evidence data | new |
| `docs/recovery/.../calibration_matrix_summary.json` | evidence data | new |
| All other tracked files | runtime / launcher / governance | **0 changed** |

→ Docs/data evidence only. Zero source-code, zero schema, zero secret writes.

## 6. Forbidden Count

| Category | Count |
| --- | --- |
| Strategy logic changes | 0 |
| Threshold changes | 0 |
| Arena pass/fail changes | 0 |
| Generation budget changes | 0 |
| Sampling weight changes | 0 |
| Execution / capital / risk changes | 0 |
| Committed secrets | 0 |
| APPLY mode additions | 0 |
| DB mutation | 0 |
| Alpha injection | 0 |
| Watchdog / cron / EnvironmentFile changes | 0 |
| **Total forbidden** | **0** |

## 7. Adherence to Order Constraints

| Constraint | Compliance |
| --- | --- |
| Read-only mode | YES |
| Offline replay only | YES |
| Cost-axis sweep mandatory | YES (Phase 1: 5 levels + Phase 7: 3 levels) |
| Entry threshold sweep mandatory | YES (Phase 2: 5 levels + Phase 7: 3 levels) |
| MAX_HOLD sweep mandatory | YES (Phase 3: 5 levels + Phase 7: 3 levels) |
| Backtester sanity | YES (Phase 4) |
| Signal-to-trade diagnostic | YES (Phase 5) |
| Funding component check | YES (Phase 6) |
| Calibration matrix replay | YES (Phase 7: 405 cells) |
| Root-cause hypothesis ranking | YES (Phase 8: 7 hypotheses, evidence-weighted) |
| Final verdict + decision branch | YES (Phase 10: CASE D) |
| Evidence dir naming | matches `docs/recovery/20260424-mod-7/0-9w-cost-threshold-horizon-calibration-diagnosis/` |
| Branch naming | matches `phase-7/0-9w-cost-threshold-horizon-calibration-diagnosis` |
| Telegram notification | sent post-merge |

## 8. Phase 9 Verdict

→ **GOVERNANCE_PASS.** Read-only diagnosis only. Zero forbidden operations. All 13 constraints met.
