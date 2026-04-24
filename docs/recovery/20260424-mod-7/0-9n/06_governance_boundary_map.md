# 06 — Governance Boundary Map

TEAM ORDER 0-9N §9.5 + §15 deliverable.

## 1. Purpose

Classify every future action in the black-box optimization program by:

- **Risk level** (Low / Med / High / Critical)
- **Order class** (documentation / telemetry / trace / generation-policy / threshold / CANARY / rollout)
- **Authorization requirement** (already-authorized vs requires-new-j13-order)
- **Gate coverage** (Gate-A + Gate-B under current post-0-9F/0-9I/0-9M regime)

## 2. Permission matrix

| # | Future task type | Example | Risk | Order class | Requires j13 separate authorization? | Gate coverage |
|--:|---|---|---|---|---|---|
| 1 | Documentation-only | Architecture report, design doc, roadmap | Low | Documentation | No — current 0-9N authorization covers | Gate-A + Gate-B on PR |
| 2 | Telemetry-only (aggregate counters) | `arena_batch_metrics` emission wiring | Low-Med | Telemetry / Trace-only | YES — P7-PR4-LITE order | Gate-A + Gate-B; controlled-diff `EXPLAINED_TRACE_ONLY` per 0-9M |
| 3 | Trace-native runtime instrumentation | A2 / A3 `_emit_lifecycle_safe()` call sites | Med | Trace-only | YES — P7-PR4-LITE / P7-PR5 order | Same — trace-only auth |
| 4 | Feedback optimizer design | Scoring formula spec | Low | Documentation | No — covered by 0-9N | Gate-A + Gate-B |
| 5 | Feedback optimizer implementation | Budget allocator code | **High** | Generation-policy (affects alpha production) | YES — 0-9O order | Gate-A + Gate-B; **may require CANARY before production** |
| 6 | Alpha generation POLICY change | Shift budget weights | **High** | Generation-policy | YES — 0-9O or 0-9R order | Gate-A + Gate-B; CANARY recommended |
| 7 | Alpha generation INTERNALS change | GP operator change, fitness function tweak | **Critical** | Alpha-logic | YES — explicit alpha-logic order | Gate-A + Gate-B + CANARY + dedicated review |
| 8 | Threshold change (A2_MIN_TRADES etc.) | `A2_MIN_TRADES: 25 → 20` | **Critical** | Threshold | YES — explicit threshold order | Gate-A + Gate-B + CANARY; `FORBIDDEN_THRESHOLD` at `zangetsu_settings_sha` enforces this |
| 9 | Arena pass/fail predicate change | Change `non_positive_pnl` to `negative_pnl_above_epsilon` | **Critical** | Arena-logic | YES — explicit Arena-logic order | Gate-A + Gate-B + CANARY |
| 10 | Champion promotion change | Change `deployable_count` semantics | **Critical** | Promotion | YES | Gate-A + Gate-B + CANARY |
| 11 | Execution / capital / risk change | Adjust position sizing, broker parameter | **Critical** | Execution | YES — explicit execution order | Gate-A + Gate-B + CANARY; paused-Arena required |
| 12 | CANARY activation | Run optimizer in live arena limited window | **High** | CANARY | YES — explicit CANARY order | Separate CANARY order; pre-requires 0-9O + 0-9R |
| 13 | Production rollout | Remove Arena freeze, enable full-traffic optimizer | **Critical** | Production | YES — explicit rollout order | CANARY evidence + Gate-A + Gate-B + human sign-off |
| 14 | Test-only additions | New behavior-invariance tests | Low | Documentation / Test | Depends on order scope | Gate-A + Gate-B |
| 15 | Governance tooling change (diff_snapshots, gates) | Add new classification | Med | Governance | YES — explicit governance order (like 0-9M) | Gate-A + Gate-B |
| 16 | Emission schema v2 (breaking) | Change `arena_batch_metrics` v1 → v2 | Med-High | Telemetry | YES — explicit versioning order | Gate-A + Gate-B; requires reader/consumer update in same order |
| 17 | External export (telemetry → external system) | Push metrics to Grafana / monitoring | Med | Observability | YES — security review | New order |
| 18 | CANARY abort | Terminate live canary, revert state | Low | Safety | No if standing abort procedure is in place | Safety order pre-authorizes this |
| 19 | Profile deprecation | Remove a profile from active pool | Med | Generation-policy | YES | Gate-A + Gate-B |
| 20 | Manual alpha injection (hand-written alpha) | Bypass GP, inject specific formula | High | Alpha-logic | YES — explicit injection order | Out of 0-9N scope |

## 3. Order-class → scope limits

| Order class | May change | May NOT change |
|---|---|---|
| Documentation | docs/**, design docs | any runtime file |
| Telemetry / Trace-only | arena runtime file SHA via trace-emission helper; tests; docs | Arena decision logic; thresholds; pass/fail predicates |
| Generation-policy | generator config; budget allocator; profile fingerprint; docs; tests | Arena decision logic; thresholds; pass/fail predicates |
| Threshold | specific constant in `zangetsu/config/settings.py` or `arena_gates.py`; docs; tests | Anything else |
| Arena-logic | `arena_pipeline.py` / `arena23_orchestrator.py` / `arena45_orchestrator.py` decision predicates; docs; tests | Alpha-logic; execution; capital |
| Promotion | `admission_validator`; champion selection logic; docs; tests | Threshold; Arena predicate |
| Execution | broker integration; position sizing; docs; tests | Arena; alpha |
| CANARY | operator runbook; canary-specific config; docs | Production defaults |
| Production | production defaults; deployment; docs | — (highest-risk; requires CANARY evidence) |
| Governance | `scripts/governance/`, `docs/recovery/**`, `state_diff_acceptance_rules.md`; docs; tests | any runtime file beyond governance |

## 4. Governance invariant protection (always-on — not overridable by any order below)

| Invariant | Protector |
|---|---|
| signed PR-only | branch protection + required_signatures |
| Linear history on main | branch protection + linear_history |
| No force push | branch protection |
| No branch deletion | branch protection |
| Admin enforcement | branch protection + enforce_admins |
| No arena respawn from governance PR | `HARD_FORBIDDEN_NONZERO` in `diff_snapshots.py` + controlled-diff |
| No engine.jsonl growth from governance PR | same |
| Threshold SHA change never trace-only-authorizable | `NEVER_TRACE_ONLY_AUTHORIZABLE` in `diff_snapshots.py` (0-9M) |
| ≥ 1 signed commit in every PR's history | Gate-A step 1.4 + merge commit signing |
| controlled-diff classifier unchanged without explicit governance order | `scripts/governance/` path governance |

## 5. Forbidden escalation paths

These escalations are NOT authorized under any order class below the specified order class:

- **Documentation → Threshold change**: NO. Even if a doc describes a proposed threshold change, the change itself requires explicit threshold order. Docs can only RECOMMEND.
- **Telemetry → Generation-policy**: NO. Telemetry emits metrics; it does NOT shift budget. Budget shift requires generation-policy order.
- **Generation-policy → Threshold**: NO. Generation-policy tunes GP parameters but does NOT change Arena floors.
- **Arena-logic → Threshold**: NO. A predicate re-expression requires Arena-logic order; a constant value change requires threshold order. Separate orders even if related.
- **CANARY → Production**: NO. Successful CANARY is evidence FOR, not authorization FOR, production rollout. Production rollout needs explicit order.
- **Any order → branch protection weakening**: NO, always.

## 6. Already-authorized (post-0-9N) scope

Within the 0-9N order itself, the following is authorized:

- Create design documents under `docs/recovery/20260424-mod-7/0-9n/` or sibling path.
- Create pre/post snapshots for controlled-diff self-check.
- Open a signed PR for the 10 design artifacts.
- Merge after Gate-A + Gate-B pass.

The following is NOT authorized under 0-9N, and is explicitly deferred to future orders:

- Any runtime code change (Arena / alpha / execution).
- Any telemetry emission insertion into runtime files.
- Any threshold / predicate / promotion change.
- CANARY / production rollout.

## 7. Recommended next-order chain

```
0-9N (documentation, this order)
  ↓ authorizes design ingestion
P7-PR4-LITE (telemetry implementation)
  - Adds arena_batch_metrics emission to arena_pipeline / arena23_orchestrator
  - Uses 0-9M's --authorize-trace-only config.<arena_file>_sha
  - Controlled-diff: EXPLAINED_TRACE_ONLY
  ↓
0-9O (feedback optimizer implementation)
  - Generation profile aggregator + scoring + budget allocator
  - Runtime config change (generator reads budget from allocator)
  - Requires generation-policy order class
  - Controlled-diff: EXPLAINED_TRACE_ONLY for arena_pipeline; EXPLAINED for new allocator
  ↓
0-9R (sparse-candidate policy tuning)
  - Generation-policy change; may include specific profile changes
  - If involves threshold change → requires SEPARATE threshold order
  - Gate-A + Gate-B + behavior-invariance
  ↓
0-9S (CANARY activation)
  - Arena unfreeze required; coordinated with 0-9R or separate
  - Live A/B measurement; bounded scope (e.g., 1 symbol, 1 week)
  - Explicit CANARY governance order
  ↓
0-9T (production rollout) — only after CANARY evidence
  - Full-traffic rollout of optimizer + policy
  - Requires explicit production order + human sign-off
```

## 8. STOP boundary enforcement

Across all future orders, STOP is triggered when:

- Any action exceeds the authorized order class per the matrix in §2.
- Any invariant in §4 is about to be violated.
- Any escalation forbidden by §5 is attempted.
- `controlled-diff` emits FORBIDDEN (including subclasses) without corresponding `--authorize-trace-only` + behavior-invariance tests.
- Gate-A or Gate-B fails.
- Tests fail.

The goal is: **every future step is explicitly governed; no step can silently escalate its scope**.
