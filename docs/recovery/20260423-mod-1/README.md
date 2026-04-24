# Zangetsu MOD-1 — System Reconstruction & Modularization Entry (Execution Record)

**Order source**: `/home/j13/claude-inbox/0-2` — "MOD-1 TEAM ORDER — ZANGETSU SYSTEM RECONSTRUCTION & MODULARIZATION ENTRY"
**Execution window**: 2026-04-23T02:30Z → 2026-04-23T03:50Z (≈1h20m, documentation-only)
**Lead**: Claude (Command)
**Team state**: Gemini CLI broken Mac-side (B7 from 0-1) — self-adversarial voice applied per §1 "two parallel voices" per CLAUDE.md §1; Codex not spawned (no executor work in MOD-1 scope).
**Status**: **ALL 8 MANDATORY + 3 OPTIONAL DELIVERABLES COMPLETE.** Phase 1–6 exit conditions met. Stop conditions: none triggered.

---

## 1. Deliverables index

All live in this directory: `/home/j13/j13-ops/docs/recovery/20260423-mod-1/`.

### Mandatory (8 of 8)

| # | File | Phase | Source strategy |
|---:|---|---|---|
| 1 | `intended_architecture.md` | Phase 1 | MOD-1 envelope + Ascension phase-1 v2.1 full content (Gemini ACCEPTED) |
| 2 | `actual_architecture.md` | Phase 2 | MOD-1 envelope + post-0-1 deltas + Ascension phase-1 v2.1 full content |
| 3 | `architecture_drift_map.md` | Phase 3 | MOD-1 envelope + post-0-1 new drifts D-24/D-25/D-26 + Ascension phase-1 v2.1 |
| 4a | `module_boundary_map.md` | Phase 4 | MOD-1 envelope + **7 full 14-field contracts (engine_kernel / gate_registry / obs_metrics / gov_contract_engine / search_contract / eval_contract / adapter_contract)** + Ascension phase-2 boundary table |
| 4b | `module_contract_template.md` | Phase 4 | **NEW** — canonical 14-field template with §4 acceptance checklist + §5 anti-patterns |
| 5 | `modular_target_architecture.md` | Phase 5 | MOD-1 envelope + state/config/control ownership cross-links + Ascension phase-2 v2.1 |
| 6a | `control_plane_blueprint.md` | Phase 6 | MOD-1 envelope + post-0-1 §17.3 note + Ascension phase-2 v2.1 (governs all 5 surface classes A-E) |
| 6b | `modularization_execution_gate.md` | Phase 6 | **NEW** — Gate-A / Gate-B / Gate-C hard conditions + §5 enforcement locations |

### Optional (3 of 3 delivered — MOD-1 §"Optional but preferred" fully covered)

| # | File | Purpose |
|---:|---|---|
| o1 | `module_registry_spec.md` | MOD-1 envelope + Ascension phase-2 v2.1 (CI/CD-hook sync, fail-closed mismatch policy) |
| o2 | `state_ownership_matrix.md` | **NEW** — every persistent state element mapped to single owner + multi-writer resolution plan |
| o3 | `control_surface_matrix.md` | **NEW** — 59 concrete control surfaces × 6 classes × decision rights + audit tier |

---

## 2. Mandatory questions — answers

### Q1. What is the minimum coherent definition of complete-form Zangetsu?

Zangetsu is an **Alpha Operating System** — a layered engine platform (9-layer target, see `intended_architecture.md §2`) that:
- discovers candidate alphas via pluggable search engines (L4 under SearchEngine contract)
- evaluates them on out-of-sample slices with honest gates (L5 + L6)
- promotes survivors through an explicit arena state machine (L2 kernel)
- publishes deployable results with versioned schemas (L7)
- is governed by a single Control Plane (L1) with decision-rights + audit
- is observed + enforced by L8 (merged observability + governance)
- wraps black-box peers via the L9 adapter pattern when needed

Minimum completeness = every module has a 14-field contract (`module_contract_template.md`) registered in the registry (`module_registry_spec.md`) with runtime validation via gov_reconciler.

### Q2. Which current parts are truly core and must be preserved?

Per Charter §2.3 + Ascension §2.3 + `intended_architecture.md §1`:
- Arena state machine (A1 → A2 → A3 → A4 → A5 → Deployable)
- Broad / semi-random search (GP is one peer; LGBM / factor-zoo / hand-seed are peers behind contract)
- Data ingestion + parquet store + indicator cache
- Backtester
- V10 gates (CD-14 holdout OOS now contract-mandated)
- staging / fresh / rejected / telemetry tables
- Policy layer (when wired — currently inert per D-04)
- Family-aware routing (future wired surface)
- Exception overlay
- Calcifer §17.3 outcome-watch (formalized commit `ae738e37`)

### Q3. Which current parts are formulation-specific and must not define future architecture?

- 60-bar forward return target (proven non-productive per G2-FAIL; do not bake into modules)
- GP-as-sole-search assumption (D-07 HIGH drift)
- Hardcoded threshold defaults in `services/*.py` (D-03 — 5 sites, must collapse into `gate_registry`)
- `alpha_signal.py` long-on-rank sign convention (Phase 3B bug; future fix lives in `search_gp` contract, not assumed)
- `pset_v0` primitive set (not a permanent fixture — `primitive_registry` must support peer psets)

### Q4. Which current parts are script-centric and must become engine-centric?

- `services/arena_pipeline.py` main loop → `search_gp` + `kernel_dispatcher` + `eval_a1`
- `services/arena23_orchestrator.py` → `kernel_dispatcher` + `eval_a2_holdout` + `eval_a3_train` + `gate_a2` + `gate_a3`
- `services/arena45_orchestrator.py` → `kernel_dispatcher` + `eval_a4_gate` + `eval_a5_tournament` + `gate_a4` + `gate_promote` + `pub_db`
- `services/shared_utils.py::claim_champion/release_champion/reap_expired_leases` → `kernel_lease` + `kernel_state`
- `services/arena13_feedback.py` → `obs_metrics` (guidance stream producer) + `gov_contract_engine` (weight-delta cap)
- `scripts/zangetsu_snapshot.sh` → `pub_snapshot` + `obs_view`
- `scripts/r2_n4_watchdog.py` pattern → `obs_freshness` generalization template
- `scripts/signal_quality_report.py` / `v10_*` / `v8_vs_v9_metrics.py` → `obs_reports`
- `scripts/verify_no_archive_reads.sh` → `gov_contract_engine`
- `zangetsu_ctl.sh` → `cp_cli` (shim, wraps new CP API)

Full list in `module_boundary_map.md §4` (preserved Ascension sanity map).

### Q5. Which responsibilities are currently mixed inside the same subsystem?

- **Arena orchestrators mix kernel + evaluation + gate logic** (D-02, D-18): each of arena23/45_orchestrator owns state machine portions, evaluator invocation, and gate thresholds in the same file
- **admission_validator is gate + kernel-writer**: DB function both evaluates gates and INSERTs into `fresh` (D-18)
- **Settings.py mixes CP params + gate thresholds + cost model** (D-03)
- **Calcifer supervisor mixes maintenance + outcome watch + Telegram notifier** (now partly separated by `ae738e37`: `zangetsu_outcome.py` is standalone module; maintenance remains in supervisor)
- **`arena_pipeline.py` mixes GP primitive registration + fitness call + DB IO + data loading** (D-02)

### Q6. Which states and configs remain scattered or hidden?

Per `architecture_drift_map.md` D-01, D-03, D-11, D-17 + `actual_architecture.md §5` + `scattered_config_map.md` (Ascension phase-1) + `state_ownership_matrix.md`:

- **Thresholds**: 5 sites for `entry/exit rank-cutoff` semantic (D-03)
- **Gate rules**: 5 authors (PL/pgSQL, orchestrator code, settings.py, yaml, Calcifer block) — D-08
- **Cost model**: hardcoded per-tier bps in `settings.py` + literals in orchestrator files
- **Cron schedules**: `crontab -l` content not in repo; install path unknown
- **Hooks + plists**: `~/.claude/hooks/*.sh` + launchd plists editable directly without integrity check (D-17)
- **DB schema-hash attestation**: missing (D-21 paired with CS-05)
- **`arena13_feedback` env**: `ZV5_DB_PASSWORD` expected at runtime but not present in cron env (D-25 new)
- **miniapps**: `d-mail-miniapp` + `calcifer-miniapp` entirely off VCS (D-24 new CRITICAL)

### Q7. Which modules must exist before full modularization can begin safely?

Per `modularization_execution_gate.md §2` Gate-A:
- `cp_api`, `cp_storage`, `cp_audit` (the CP skeleton) — BLOCKER D-01 resolution
- `obs_metrics` + `gov_contract_engine` (Gate-B.B.2 shadow observation requires these)
- `kernel_state` + `kernel_dispatcher` (state-machine authority — prerequisite for any evaluator/gate/publisher migration)
- CS-05 detection mechanism (pg-hash manifest reconciler) — BLOCKER mitigation

### Q8. Which proposed modules may remain black-box internally?

Per Charter §3.6 + `module_boundary_map.md §MOD-1.B Module 7` + `blackbox_adapter_contracts.md`:
- `search_lgbm` (future LGBM peer) — WHEN it lands, declare `blackbox_allowed: true` with LGBM wrapped by adapter_contract
- `search_transformer` / other ML search (hypothetical) — same
- External LLM adapters (Gemini / Codex / Markl / Calcifer Gemma4) — when integrated as runtime control-path, wrapped by adapter

All require:
- `blackbox_pattern_applied: true` in module registry entry
- 13 mandatory adapter fields populated
- Integrity hash verification at load
- non_determinism_detected + resource_exhaustion failure modes declared (Gemini §F.2 v2)
- RED Telegram on any adapter failure (Gemini §H.3)

### Q9. Which proposed modules must remain fully transparent and auditable?

Per `module_contract_template.md §2 field 13` (`blackbox_allowed: false` by default):
- `cp_api`, `cp_storage`, `cp_audit`, `cp_worker_bridge`, `cp_cli`, `cp_notifier` — Control Plane is the white-box authority
- `kernel_state`, `kernel_lease`, `kernel_dispatcher`, `kernel_logger` — state machine authority
- `gate_*` (all gate modules) — rejection logic must be explicit per Charter §3.3
- `eval_contract` + non-ML evaluators — orchestration + deterministic math
- `gov_*` (all governance modules) — policy engine must be fully readable
- `obs_metrics`, `obs_logs`, `obs_view`, `obs_reports`, `obs_freshness` — observability data plane

### Q10. What must remain deferred until recovery baseline strengthens further?

Per 0-2 Phase 4 defer list + `modularization_execution_gate.md`:
- Broad refactor (forbidden by 0-2 §SCOPE)
- Service migration (Gate-A blocks until 7-day quiescence + Gemini accepts MOD-1)
- Console implementation (Gate-C.C.1 blocks until ≥30d CP uptime)
- Runtime takeover by control plane (Gate-C blocks)
- Track 3 discovery restart (see `../20260423/track3_restart_memo.md`)
- Arena service formalization (see `../20260423/systemd_deferral_memo.md`)
- Policy / discovery merge into recovery (Charter §2.5 perpetual ban)
- Production deployment beyond already-approved recovery work (0-2 §OUT OF SCOPE)

---

## 3. Non-negotiable rules compliance (0-2 §NON-NEGOTIABLE)

| Rule | Compliance | Evidence |
|---|---|---|
| 1. No silent production mutation | ✅ | Every mutation in docs + commits |
| 2. No discovery restart | ✅ | No arena restart; `track3_restart_memo.md` still authoritative |
| 3. No systemd enablement for arena | ✅ | `systemd_deferral_memo.md` still authoritative |
| 4. No Phase3e mixed merge | ✅ | phase3e worktree unchanged at 480976c1 |
| 5. No broad mainline refactor | ✅ | Zero code changes in MOD-1 (doc-only) |
| 6. No threshold or gate change | ✅ | Zero config touched |
| 7. No recovery-path contamination | ✅ | MOD-1 docs separate from `docs/recovery/20260423/` R2 docs; cross-referenced, not merged |
| 8. No black-box control surface | ✅ | `control_surface_matrix.md` enumerates 59 surfaces all with owner + decision rights + audit tier |
| 9. No module without 14-field contract | ✅ | `module_contract_template.md` + 7 mandatory contracts in `module_boundary_map.md §MOD-1.B` |
| 10. Labels applied | ✅ | VERIFIED/PROBABLE/INCONCLUSIVE/DISPROVEN used throughout |

## 4. Stop conditions (0-2 §STOP CONDITIONS)

| Condition | Occurred? |
|---|---|
| Mutated production | NO |
| Changed thresholds or gates | NO |
| Restarted arena services | NO |
| Mixed modularization with Track 3 restart | NO |
| Mixed modularization with broad recovery patching | NO |
| Proposed black-box control surface | NO |
| Proposed module migration without rollback boundary | NO — every contract has `rollback_surface` |
| Proposed console ownership without explicit state/config contracts | NO — `control_surface_matrix.md` + `state_ownership_matrix.md` provide both |

## 5. MOD-1 success criteria (0-2 §SUCCESS CRITERIA)

| Criterion | Met? | Evidence |
|---|---|---|
| 1. Intended architecture explicit | ✅ | `intended_architecture.md` §MOD-1.B–§MOD-1.E |
| 2. Actual architecture explicit | ✅ | `actual_architecture.md` §MOD-1.B–§MOD-1.E |
| 3. Drift explicit | ✅ | `architecture_drift_map.md` §MOD-1 + 23 base drifts + 3 new drifts |
| 4. Module boundaries explicit | ✅ | `module_boundary_map.md` §MOD-1.B (7 contracts) + Ascension §2 (46-module table) |
| 5. Target modular engine architecture coherent | ✅ | `modular_target_architecture.md` §MOD-1 cross-links to state/config/control ownership matrices |
| 6. First control-plane blueprint exists | ✅ | `control_plane_blueprint.md` covers §4.1–§4.5 surface classes A–E |
| 7. Modularization implementation remains gated | ✅ | `modularization_execution_gate.md` Gate-A/B/C hard conditions defined; current earliest Phase-7 = 2026-04-30 |
| 8. No recovery judgment contaminated | ✅ | MOD-1 docs explicitly separate from recovery corpus; `r2_recovery_review.md` not modified |

## 6. Q1/Q2/Q3 self-audit

**Q1 Adversarial (5 dimensions)** — PASS
- Input boundary: 7 mandatory modules + 3 optional matrices + 1 template + 1 gate = 12 deliverables explicit; plus post-0-1 deltas captured in 3 envelopes
- Silent failure: arena13_feedback KeyError + calcifer tree pollution + gemini CLI breakdown + miniapps off-VCS all explicitly labeled
- External dep: Gemini CLI reliance called out as B7; self-adversarial fallback documented
- Concurrency: state_ownership_matrix forces SHARED writers to be enumerated; execution_gate Gate-C.C.3 requires ≤20% scatter residual before control-plane takeover
- Scope creep: zero code; zero service restart; zero threshold change

**Q2 Structural Integrity** — PASS
- Every deliverable has tested base (Ascension v2.1 Gemini-accepted) OR explicit Q1 adversarial for fresh content (template + gate + 2 matrices)
- No silent failure propagation — each module contract declares `failure_surface` with 7 minimum categories

**Q3 Execution Efficiency** — PASS
- 1h20m wall clock for documentation-only MOD-1
- Leveraged 17 existing Ascension docs (3,453 lines) rather than duplicating work
- Wrote 4 new (template + gate + 2 matrices) + 7 envelope wrappers + 1 README = 12 files

## 7. Handoff to MOD-2

Per 0-2 §FINAL ORDER: "Deliver the documents. Then wait for MOD-2."

MOD-1 is delivered. All 8 mandatory + 3 optional files in place. Phase-7 (implementation) is blocked by `modularization_execution_gate.md` Gate-A conditions:
- A.1 Gemini round-2 on MOD-1 outputs (pending — Gemini CLI B7 resolution required)
- A.2 7-day quiescence (earliest clearing 2026-04-30)
- A.3 Scope freeze on recovery-path (HOLDING)

**Awaiting MOD-2 order.**

---

## 8. File index (absolute paths)

```
/home/j13/j13-ops/docs/recovery/20260423-mod-1/
├── README.md                              (this file)
├── intended_architecture.md               (Phase 1)
├── actual_architecture.md                 (Phase 2)
├── architecture_drift_map.md              (Phase 3)
├── module_boundary_map.md                 (Phase 4a — with 7 module contracts)
├── module_contract_template.md            (Phase 4b — NEW template)
├── modular_target_architecture.md         (Phase 5)
├── control_plane_blueprint.md             (Phase 6a)
├── modularization_execution_gate.md       (Phase 6b — NEW gate)
├── module_registry_spec.md                (Optional)
├── state_ownership_matrix.md              (Optional — NEW)
└── control_surface_matrix.md              (Optional — NEW)
```

Cross-references:
- `../20260423/` — 0-1 recovery corpus (R2 formalization + infra blockers + systemd/Track-3 deferrals)
- `../../../zangetsu/docs/ascension/` — authoritative source of v2.1 ACCEPTED Ascension content embedded in MOD-1 envelopes
- `../../../calcifer/` — §17.3 outcome watch (`zangetsu_outcome.py` + `supervisor.py`) commit `ae738e37`
