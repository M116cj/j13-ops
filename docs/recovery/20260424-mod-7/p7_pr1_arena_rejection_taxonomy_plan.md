# P7-PR1 Arena Rejection Taxonomy Plan

- **Scope**: First Phase 7 PR. Scope STRICTLY limited to telemetry + rejection enum + tracing + logging adapter + test fixtures + governance docs. No alpha logic, no threshold, no production execution change, no champion promotion change, no Arena 2 pass/fail relaxation (0-9 §5 forbidden list).
- **Actions performed**:
  1. Inventoried the 16 required minimum reject categories from 0-9 §3 P7-M1.
  2. Sketched module contract skeleton for `arena_telemetry` module.
  3. Enumerated allowed file paths + forbidden file paths.
  4. Defined PR structure per 0-9 §4 (12-field PR body).
  5. HALTED — no signed commit can be produced from Alaya; P7-PR1 cannot be executed under current conditions.
- **Evidence path**:
  - 0-9 §3 P7-M1 required output list
  - 0-9 §5 first authorized PR allowed/forbidden lists
  - 0-9 §4 required PR structure (12 fields)
  - 0-9 §6 Gate-B enforcement expectations
- **Observed result — planned P7-PR1 content**:

### Allowed files (target paths, pending signed-commit flow)
- `zangetsu/src/modules/arena_telemetry/reject_reason.py` — enum of exactly 17 categories (16 minimum + UNKNOWN_REJECT)
- `zangetsu/src/modules/arena_telemetry/arena_counters.py` — counter schema + accumulator
- `zangetsu/src/modules/arena_telemetry/candidate_trace.py` — candidate_id + alpha_id + formula_hash traceability
- `zangetsu/src/modules/arena_telemetry/stage_transition.py` — stage transition log (A0→A1→A2→A3→promotable)
- `zangetsu/src/modules/arena_telemetry/deployable_source_trace.py` — deployable_count source trace
- `zangetsu/src/modules/arena_telemetry/arena2_decomposition.py` — ARENA2_REJECTED breakdown
- `zangetsu/module_contracts/arena_telemetry.yaml` — 15-field module contract
- `zangetsu/tests/modules/arena_telemetry/test_reject_reason.py`
- `zangetsu/tests/modules/arena_telemetry/test_arena_counters.py`
- `zangetsu/tests/modules/arena_telemetry/test_candidate_trace.py`
- `zangetsu/tests/modules/arena_telemetry/test_stage_transition.py`
- `zangetsu/tests/modules/arena_telemetry/fixtures/` — golden reject-reason fixtures
- `docs/decisions/YYYYMMDD-module-arena_telemetry.md` — ADR with Gemini ACCEPT record
- `docs/rollback/arena_telemetry.md` — rollback runbook

### Forbidden files (explicit do-not-touch list)
- `zangetsu/services/arena_pipeline.py` (alpha formula / candidate scoring)
- `zangetsu/services/arena23_orchestrator.py` (Arena 2/3 thresholds)
- `zangetsu/services/arena45_orchestrator.py` (promotion thresholds)
- `zangetsu/engine/components/alpha_*` (formula mutation)
- `zangetsu/config/settings.py` (thresholds)
- Any admission_validator PL/pgSQL (gate semantics)
- Any Calcifer block-file logic (runtime semantics)

### Reject reason enum (17 values — 16 minimum + UNKNOWN_REJECT)
```python
class RejectReason(str, Enum):
    INVALID_FORMULA = "INVALID_FORMULA"
    UNSUPPORTED_OPERATOR = "UNSUPPORTED_OPERATOR"
    WINDOW_INSUFFICIENT = "WINDOW_INSUFFICIENT"
    NON_CAUSAL_RISK = "NON_CAUSAL_RISK"
    NAN_INF_OUTPUT = "NAN_INF_OUTPUT"
    LOW_BACKTEST_SCORE = "LOW_BACKTEST_SCORE"
    HIGH_DRAWDOWN = "HIGH_DRAWDOWN"
    HIGH_TURNOVER = "HIGH_TURNOVER"
    COST_NEGATIVE = "COST_NEGATIVE"
    FRESH_FAIL = "FRESH_FAIL"
    OOS_FAIL = "OOS_FAIL"
    REGIME_FAIL = "REGIME_FAIL"
    SIGNAL_TOO_SPARSE = "SIGNAL_TOO_SPARSE"
    SIGNAL_TOO_DENSE = "SIGNAL_TOO_DENSE"
    CORRELATION_DUPLICATE = "CORRELATION_DUPLICATE"
    PROMOTION_BLOCKED = "PROMOTION_BLOCKED"
    UNKNOWN_REJECT = "UNKNOWN_REJECT"   # must NOT dominate; > 5% → SHADOW cap
```

### Acceptance criteria per 0-9 §3 P7-M1
- UNKNOWN_REJECT exists but does not dominate. If UNKNOWN_REJECT > 5% after migration → PR cannot be promoted beyond SHADOW.

### PR body template (12 fields per 0-9 §4)
1. Migration scope: P7-M1 Arena Rejection Taxonomy + Telemetry Baseline
2. Files changed: [list]
3. Runtime behavior impact: NONE (telemetry only; pure additive in `zangetsu/src/modules/arena_telemetry/`)
4. Forbidden changes statement: no alpha/threshold/gate-semantics/champion-promotion touched; verified by file-path allowlist
5. Test evidence: unit + contract tests + golden fixtures, coverage ≥ 85%
6. Gate-A result: [PR # + workflow run URL]
7. Gate-B result: [per-module check outcomes]
8. Controlled-diff result: before/after snapshot pair; classification = EXPLAINED (telemetry additions) + ZERO FORBIDDEN
9. SHADOW plan: [link to shadow_plan doc]
10. CANARY plan: [link to canary_plan doc]
11. Rollback path: [link to rollback runbook]
12. Go/No-Go verdict: pending Gemini adversarial on this PR

- **Forbidden changes check**: This plan only ENUMERATES the target scope; it does not implement any of it. No code was written to Alaya git tree. No commit attempted.
- **Residual risk**:
  - Plan is unexecuted due to signing blocker. The plan itself is correct and implementable; the blocker is governance/infrastructure (signed-commit capability from Alaya), not scope.
  - When execution resumes (post signing resolution), this plan is the blueprint.
- **Verdict**: PLAN APPROVED FOR EXECUTION UNDER SIGNED FLOW. Execution halted pending signing capability per 0-9 §10.
