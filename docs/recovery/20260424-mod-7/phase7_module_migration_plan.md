# Phase 7 Module Migration Plan

- **Scope**: Ordered migration sequence P7-M1 through P7-M6 per 0-9 §3. Each Mx defines scope, allowed-forbidden fields, and verdict target.
- **Actions performed**: Transcribed 0-9 §3 into an authoritative plan; added Gate-B enforcement annotations per Mx.
- **Evidence path**: 0-9 §3 modules + §5 first-PR scope + §6 Gate-B expectations.
- **Observed result — migration order (condition-based; not date-based)**:

| Order | Module | Verdict target | Key "allowed" | Key "forbidden" |
|---|---|---|---|---|
| P7-M1 | Arena Rejection Taxonomy / Telemetry First | Unified reject_reason schema + counters + candidate/alpha traceability + deployable_count source trace | reject_reason enum, counters schema, tracing, logging adapter | changing alpha scoring, lowering Arena 2 thresholds |
| P7-M2 | Arena 0 Regression Lock | REGRESSION_LOCKED | tests, logging, regression fixtures | ranking-logic change, threshold change, weakening rules |
| P7-M3 | Arena 1 Scoring Stability | OPERATIONAL_WITH_EXPLAINABLE_SCORE | backtest metric schema, fee/slippage-aware score, drawdown/turnover/hit-rate recording, sample-validity checks | lookahead bias, threshold mutation, paper-profit-only promotion |
| P7-M4 | Arena 2 Root-Cause Migration | ROOT_CAUSE_VISIBLE (does NOT need stable champions yet) | fresh/OOS diagnostics, regime-sensitivity report, deployable_count trace, rejection decomposition | lowering thresholds to generate champions, hiding rejections under generic labels |
| P7-M5 | Arena 3 Champion Stability | CHAMPION_STABILITY_VALIDATOR (only after M4 taxonomy works) | multi-symbol + multi-window robustness, correlation clustering, parameter sensitivity | starting M5 before M4 taxonomy is visible |
| P7-M6 | SHADOW + CANARY Rehearsal Framework | Every migrated module passes SHADOW and CANARY before production | live/replay SHADOW (no mutation), bounded CANARY (limited activation, rollback ready, controlled-diff clean) | promoting any module without both rehearsals recorded |

- **Forbidden changes check**: This doc does NOT execute any migration. It orders them. Each Mx execution requires its own PR, its own Gate-B run, its own SHADOW + CANARY per §6.
- **Residual risk**:
  - If P7-M1 stalls (cannot produce signed commit), ALL downstream M2–M6 are blocked because they depend on M1 reject_reason taxonomy to have explainable rejections.
  - Migration ordering is "condition-based, not date-based" per 0-6 framework — a P7-Mx module blocks the next Mx only until its verdict target is proven.
- **Verdict**: Plan recorded + ordered. Execution pending resolution of signed-commit blocker.
