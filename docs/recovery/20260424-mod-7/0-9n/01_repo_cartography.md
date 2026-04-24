# 01 — Repo Cartography (post-0-9M)

TEAM ORDER 0-9N §9.1 deliverable.

## 1. Top-level layout

```
zangetsu/
├── engine/                   # alpha generation (GP + indicator_engine)
│   ├── components/
│   │   ├── alpha_engine.py   # AlphaEngine: GP evolve(), ast_to_callable()
│   │   ├── p_value.py        # baseline + p-value computation
│   │   ├── data_preprocessor.py
│   │   └── ...
│   └── provenance.py         # ProvenanceBundle / build_bundle
├── services/
│   ├── arena_pipeline.py     # V10 main loop: evolve → A1 backtest → val gate → admission
│   ├── arena_gates.py        # arena2_pass / arena3_pass / arena4_pass + thresholds
│   ├── arena23_orchestrator.py  # A2 + A3 stage orchestration (post-admission)
│   ├── arena45_orchestrator.py  # A4 (regime) + A5 (live paper) orchestration
│   ├── arena13_feedback.py   # A13 downstream-truth feedback into A1 weights
│   ├── arena_rejection_taxonomy.py   # P7-PR1: 18 canonical reasons
│   ├── arena_telemetry.py    # P7-PR1: RejectionTrace + TelemetryCollector
│   ├── candidate_trace.py    # P7-PR1/P7-PR2/P7-PR3: CandidateLifecycle +
│   │                         # LifecycleTraceEvent + deployable_count provenance
│   ├── candidate_lifecycle_reconstruction.py  # P7-PR2/P7-PR3: post-hoc joiner
│   ├── holdout_splits.py
│   ├── regime_tagger.py
│   ├── bloom_service.py
│   ├── shared_utils.py
│   └── control_plane/cp_api/ # cp_api skeleton (write-safety middleware)
├── tests/                    # pytest test suite (169 tests post-0-9M)
├── logs/                     # engine.jsonl (308K+ lines, 7-day rolling)
│   ├── engine.jsonl
│   └── engine.jsonl.1
├── config/
│   └── settings.py           # thresholds: ENTRY_THR, EXIT_THR, MIN_HOLD, COOLDOWN
│                             # NEVER_TRACE_ONLY_AUTHORIZABLE per 0-9M
├── indicator_engine/         # Rust-backed indicator computations
└── data/                     # parquet OHLCV / funding / oi (LFS)

scripts/governance/
├── capture_snapshot.sh       # MOD-6 Phase 4 — 5-surface snapshot
└── diff_snapshots.py         # Phase 7-aware classifier (0-9M upgrade)

.github/workflows/
├── phase-7-gate.yml          # Gate-A (post-0-9F path coverage)
└── module-migration-gate.yml # Gate-B (post-0-9I trigger fix)

docs/recovery/                # per-order evidence trail
├── 20260423/                 # MOD-1/MOD-2 recovery
├── 20260423-mod-1/.../mod-4/ # MOD-1..MOD-4 era
├── 20260424-mod-5/           # MOD-5 controlled-diff framework
├── 20260424-mod-6/           # MOD-6 Phase 7 prep
├── 20260424-mod-7/           # MOD-7 Phase 7 PRs (current)
│   ├── p7_pr1_*.md            # P7-PR1 taxonomy + telemetry
│   ├── 0-9g_*.md / 0-9h_*.md  # SHADOW / mapping patch
│   ├── 0-9i_*.md              # Gate-B fix
│   ├── 0-9j_*.md              # CANARY
│   ├── 0-9k_*.md              # P7-PR2 lifecycle provenance
│   ├── 0-9l_*.md              # P7-PR3 trace contract + A1 emission
│   ├── 0-9m_*.md              # controlled-diff upgrade
│   └── 0-9n/                  # THIS ORDER
└── 20260424-mod-7a/          # MOD-7A signing unlock evidence

docs/governance/
├── snapshots/                # controlled-diff JSON snapshots per ORDER
└── 20260423-conditional-patch/  # CQG patch docs
```

## 2. Alpha generation flow (black-box — what we do NOT need to interpret per-alpha)

`arena_pipeline.py:main()` in a per-round loop:

```
for round in range(N_ROUNDS):
  for symbol in DIRECTIONAL:
    for regime in REGIMES:
      alphas = AlphaEngine.evolve(close, high, low, vol, returns,
                                  n_gen=N_GEN, pop_size=POP_SIZE, top_k=TOP_K)
      # alphas: black box — GP-evolved alpha expressions ranked by fitness

      for alpha_result in alphas:
        # A1 backtest + val gate (see §3)
        if passes_all_A1_gates:
          admit to DB → admission_validator() decides champion status
```

The inner content (`evolve`, fitness function, mutation / crossover operators) is the BLACK BOX that 0-9N explicitly chooses not to open.

## 3. Arena stage flow (white box — what we DO need visibility of)

| Stage | Location | Decision | Known rejection patterns |
|---|---|---|---|
| A0 | alpha_engine.py (implicit) | Formula validates (not NaN/Inf/constant) | INVALID_FORMULA, UNSUPPORTED_OPERATOR, NAN_INF_OUTPUT |
| A1 | arena_pipeline.py L690-820 | `bt.total_trades >= 30` AND val gates (trades>=15, net_pnl>0, sharpe>=0.3, wilson>=0.52) | `reject_few_trades`, `reject_val_neg_pnl`, `reject_val_low_sharpe`, `reject_val_low_wr`, `reject_val_constant`, `reject_val_error`, `reject_val_few_trades` |
| A2 | arena23_orchestrator.py + arena_gates.arena2_pass() | `trades >= A2_MIN_TRADES (25)` + `total_pnl > 0` | `too_few_trades` (SIGNAL_TOO_SPARSE), `non_positive_pnl` (COST_NEGATIVE), `[V10]: pos_count=0`, `[V10]: trades=N < 25`, `<2 valid indicators after zero-MAD filter` |
| A3 | arena23_orchestrator.py + arena_gates.arena3_pass() | 5-segment WR/PnL stability: WR_passes>=4 AND PnL_passes>=4 AND WR_floor>=0.45 | `validation split fail`, `train/val PnL divergence`, `A3 PREFILTER SKIP` |
| A4 | arena45_orchestrator.py + arena_gates.arena4_pass() | Regime stability (bull/bear/range) | REGIME_FAIL |
| A5 | arena45_orchestrator.py | 14-day live paper shadow | _not currently observed in logs_ |

**Thresholds (pinned, enforced by `test_arena_gates_thresholds_*_under_p7_pr*` tests)**:
- `A2_MIN_TRADES = 25`
- `A3_SEGMENTS = 5`
- `A3_MIN_TRADES_PER_SEGMENT = 15`
- `A3_MIN_WR_PASSES = 4`
- `A3_MIN_PNL_PASSES = 4`
- `A3_WR_FLOOR = 0.45`

## 4. Telemetry / provenance stack (current)

| Layer | Capability | Data source |
|---|---|---|
| P7-PR1 | 18 canonical rejection reasons + JSON serializable traces | `arena_rejection_taxonomy.py`, `arena_telemetry.py` |
| P7-PR1 | raw-string → canonical classifier (substring + prefix) | `RAW_TO_REASON` (20+ entries after 0-9H V10 patch) |
| P7-PR2 | Post-hoc CandidateLifecycle reconstruction from engine.jsonl | `candidate_lifecycle_reconstruction.py` |
| P7-PR2 | deployable_count provenance with FULL/PARTIAL/UNAVAILABLE | `derive_deployable_count_with_provenance()` |
| P7-PR3 | Unified LifecycleTraceEvent contract for A1..A5 | `candidate_trace.py` builder/parser/emitter |
| P7-PR3 | A1 trace-native emission in runtime (ENTRY, EXIT_REJECT, EXIT_PASS, HANDOFF_TO_A2) | `arena_pipeline.py` 3 call sites |
| 0-9M | Phase 7-aware controlled-diff with EXPLAINED_TRACE_ONLY | `diff_snapshots.py` |

**Not yet present (design target for 0-9N → P7-PR4-LITE)**:
- Aggregate per-stage entered/passed/rejected counters emitted as structured events
- Per-batch metrics
- Per-generation-profile metrics
- Feedback-decision-record schema

## 5. Governance surface (current state, post-0-9M)

| Control | Status |
|---|---|
| Branch protection main: enforce_admins, req_sig, linear, no-force, no-delete | INTACT |
| Signing infrastructure (ed25519 `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`) | LIVE |
| Gate-A (phase-7-gate.yml) auto-trigger on pull_request | WORKING (post-0-9F / 0-9I) |
| Gate-B (module-migration-gate.yml) auto-trigger on pull_request | WORKING (post-0-9I) |
| controlled-diff framework | Phase 7-aware (post-0-9M) |
| Test suite | 169 PASS |
| Outstanding governance exceptions | **0** |

## 6. Known bottleneck (from 0-9J CANARY / 0-9K P7-PR2 / 0-9L P7-PR3)

- **Arena 2 is 93-96.5% of all rejection traffic**.
- **88.2% of non-deployable candidates exit at A2 with `SIGNAL_TOO_SPARSE`** — candidates produce fewer than `A2_MIN_TRADES=25` trades on the A2 holdout.
- **6 deployable candidates** in the 2026-04-16 → 2026-04-23 7-day observation window (IDs 70381, 70382, 70390, 70400, 70407, 70436).
- `deployable_count` provenance = PARTIAL (A1 timestamps structurally missing until P7-PR3 emission runs on live Arena).

## 7. Black-box vs white-box boundary (per j13's 0-9N direction)

**BLACK BOX (no interpretability required)**:
- AlphaEngine.evolve() internals (GP operators, mutation, crossover, fitness)
- Per-alpha formula ancestry
- Parent-child mutation lineage
- Per-alpha semantic explanation
- Indicator sampling strategy internals

**WHITE BOX (full observability required)**:
- Arena pass/reject counts per stage per batch
- Rejection reason distribution
- Generation-profile-level pass-rate aggregates
- deployable_count source
- Per-batch feedback decisions

## 8. What 0-9N is designing (non-code)

0-9N produces a design package (10 artifacts under this dir) that becomes the input to future orders:

- **P7-PR4-LITE** implements aggregate Arena pass-rate telemetry
- **0-9O** implements generation profile scoring + feedback optimizer
- **0-9R** implements sparse-candidate policy change (no threshold relaxation)
- **0-9S** runs CANARY for the optimizer
- **0-9T** considers production rollout

0-9N itself changes **no runtime code**.
