# TEAM ORDER 0-9M — Controlled-Diff Acceptance Rules Upgrade Report

## 1. Status

**COMPLETE**

## 2. Baseline

| Field | Value |
|---|---|
| origin/main SHA | `1303ab08a35e8d078d12eef064bc5fb497b6309c` |
| local main SHA | `1303ab08a35e8d078d12eef064bc5fb497b6309c` (ahead/behind=0/0) |
| Branch | `phase-7/controlled-diff-acceptance-rules-upgrade` |
| PR URL | _filled post-PR-open_ |
| Merge SHA | _filled post-merge_ |
| Signature verification | Pre-commit: GOOD (ED25519 `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`); GitHub-side: pending PR verification |

## 3. Why 0-9M existed

TEAM ORDER 0-9L-PLUS / P7-PR3 (merge commit `1303ab08`) added authorized A1 trace-native lifecycle emission to `arena_pipeline.py`. The change was additive-only (+69 LOC; 0 decision-logic lines modified) and all 150 behavior-invariance tests passed.

However, the legacy controlled-diff tool (`scripts/governance/diff_snapshots.py`) classified `config.arena_pipeline_sha` change as `FORBIDDEN` because its model used a pure file-SHA tripwire with no understanding of "authorized trace-only instrumentation."

j13 issued a one-time exception via TEAM ORDER 0-9L-A (`0-9l_controlled_diff_exception_record.md`). That exception was explicitly not intended to become permanent operating practice — every future Phase 7 trace emission PR (P7-PR4 A2 emission, P7-PR5 A3 emission, etc.) would otherwise require its own ad-hoc exception record.

0-9M upgrades the tool to Phase 7-aware classification so authorized trace instrumentation is classified as `EXPLAINED_TRACE_ONLY` automatically, without needing per-PR exception records.

## 4. What changed

| File | Scope |
|---|---|
| `scripts/governance/diff_snapshots.py` | +70 LOC — new classification vocabulary (`EXPLAINED_TRACE_ONLY`, `FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA`, `FORBIDDEN_THRESHOLD`); new `--authorize-trace-only <field>` CLI flag; new `NEVER_TRACE_ONLY_AUTHORIZABLE` defense-in-depth list; extended `diff()` to bucket trace-only results separately; extended markdown rendering. |
| `docs/recovery/20260424-mod-5/state_diff_acceptance_rules.md` | +~120 lines — new §11 documenting 0-9M upgrade: vocabulary, decision precedence, required preconditions, defense-in-depth, migration note. |
| `zangetsu/tests/test_controlled_diff_acceptance_rules.py` | NEW +200 LOC — 19 test cases covering every classification branch. |
| `docs/recovery/20260424-mod-7/0-9m_controlled_diff_acceptance_rules_upgrade_report.md` | NEW — this report. |
| `docs/governance/snapshots/2026-04-24T111214Z-pre-0-9m.json` | NEW — pre-snapshot. |
| `docs/governance/snapshots/2026-04-24T111215Z-post-0-9m.json` | NEW — post-snapshot. |

**0 Arena runtime files modified. 0 threshold file modified. 0 alpha / promotion / execution / risk file modified.**

## 5. New classification model

```
ZERO_DIFF                          — unchanged
EXPLAINED                          — changed AND matches §2 catalog
EXPLAINED_TRACE_ONLY               — CODE_FROZEN file SHA changed AND --authorize-trace-only passed
FORBIDDEN                          — umbrella for violations
FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA — CODE_FROZEN SHA changed without authorization
FORBIDDEN_THRESHOLD                — zangetsu_settings_sha changed (NEVER authorizable)
OPAQUE                             — manifest differs, no field-level change
```

Overall verdict precedence: `FORBIDDEN` > `EXPLAINED_TRACE_ONLY` > `EXPLAINED` > `OPAQUE` > `ZERO_DIFF`. Tool exit codes: 0 for `ZERO/EXPLAINED/EXPLAINED_TRACE_ONLY`; 2 for `FORBIDDEN`; 3 for `OPAQUE`.

## 6. EXPLAINED_TRACE_ONLY conditions

A diff may classify as `EXPLAINED_TRACE_ONLY` **only when all** of these hold (enforced by order review, tests, and Gates — NOT by the tool alone):

1. Active Team Order explicitly authorizes the touched runtime file.
2. Changed code limited to: trace emission / telemetry / logging / serialization / lifecycle provenance / non-blocking observability / exception-safe instrumentation.
3. No alpha formula generation change.
4. No formula construction / mutation / crossover / search / ranking change.
5. No Arena pass/fail branch condition change.
6. No threshold constant change.
7. No champion promotion logic change.
8. No execution / capital / risk / broker / exchange / live trading change.
9. Behavior-invariance tests pass.
10. Evidence report documents: touched file, old SHA, new SHA, reason, explicit authorization source, forbidden-change audit.
11. Gate-A passes.
12. Gate-B passes.
13. Signed PR-only flow preserved.
14. Branch protection intact.

## 7. Forbidden protections preserved

All §4 forbidden protections remain intact and are NOT weakened by 0-9M:

- **Alpha generation**: `zangetsu_settings_sha` change → `FORBIDDEN_THRESHOLD` regardless of any flag. Arena runtime files where alpha generation lives (e.g. arena_pipeline.py) require explicit `--authorize-trace-only` per field; accidentally passing it does NOT excuse a non-trace-only change because behavior-invariance tests + PR review catch it.
- **Thresholds**: `NEVER_TRACE_ONLY_AUTHORIZABLE = {"config.zangetsu_settings_sha"}` — defense-in-depth refuses trace-only authorization for this field.
- **Arena pass/fail**: changes live inside `arena_pipeline.py` / `arena23_orchestrator.py` / `arena_gates.py`. Runtime SHA change without trace-only authorization = `FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA`. With trace-only authorization = `EXPLAINED_TRACE_ONLY`, but tests + Gate-A + Gate-B + PR review verify the assertion that the change is genuinely trace-only.
- **Champion promotion**: same guard as above.
- **Execution / capital / risk**: same guard.
- **Production rollout**: NOT STARTED. No CANARY. No production mutation.

## 8. Test results

```
pytest zangetsu/tests/test_arena_rejection_taxonomy.py \
       zangetsu/tests/test_arena_telemetry.py \
       zangetsu/tests/test_p7_pr1_behavior_invariance.py \
       zangetsu/tests/test_candidate_lifecycle_reconstruction.py \
       zangetsu/tests/test_deployable_count_provenance.py \
       zangetsu/tests/test_p7_pr2_behavior_invariance.py \
       zangetsu/tests/test_lifecycle_trace_contract.py \
       zangetsu/tests/test_p7_pr3_trace_native_a1_emission.py \
       zangetsu/tests/test_p7_pr3_lifecycle_fullness_projection.py \
       zangetsu/tests/test_p7_pr3_behavior_invariance.py \
       zangetsu/tests/test_controlled_diff_acceptance_rules.py
=> 169 passed, 0 failed, 1 pre-existing warning (0.93 s)
```

The 19 new 0-9M tests cover:
- Authorized trace-only runtime SHA → `EXPLAINED_TRACE_ONLY`
- Unauthorized runtime SHA → `FORBIDDEN_UNAUTHORIZED_RUNTIME_SHA`
- Threshold change (zangetsu_settings_sha) → `FORBIDDEN_THRESHOLD` even with trace-only authorization passed
- Arena pass/fail path (arena23_orchestrator_sha) → forbidden without authorization
- Champion promotion path (arena45_orchestrator_sha) → forbidden without authorization
- Calcifer supervisor → forbidden without authorization
- Hard-forbidden fields (arena process count, engine.jsonl growth) → remain forbidden under all conditions
- Zero-diff / legacy explained / legacy forbidden regressions pass
- Mixed scenarios (trace-only + explained; trace-only + forbidden) resolve correctly
- Unknown path default → forbidden
- Encoded 0-9L-PLUS historical case classifies as `EXPLAINED_TRACE_ONLY`

## 9. Controlled-diff result

**Before 0-9M (legacy model)**: 0-9L-PLUS PR #13 reported `FORBIDDEN` on `config.arena_pipeline_sha`. Required j13 one-time exception.

**After 0-9M (Phase 7-aware model)**: same snapshot diff with `--authorize-trace-only config.arena_pipeline_sha` classifies as `EXPLAINED_TRACE_ONLY`. The `test_0_9l_plus_historical_case_classifies_as_explained_trace_only` test asserts this.

**0-9M self-test** (running controlled-diff on 0-9M's own changes): classification = `EXPLAINED`, 43 zero-diff / 1 explained / 0 forbidden / 0 trace-only. The changes to `scripts/governance/diff_snapshots.py` do not touch any `CODE_FROZEN` field because `diff_snapshots.py` is not captured in the snapshot's `config.*_sha` field list (only specific runtime + config files are tracked).

| Metric | 0-9M self-diff |
|---|---|
| Classification | **EXPLAINED** |
| Zero diff | 43 fields |
| Explained diff | 1 field (`repo.git_status_porcelain_lines 3 → 4`) |
| Explained trace-only | 0 fields |
| Forbidden | **0** |

## 10. Gate-A result

_Filled post-PR-open_. Expected: triggered on pull_request + PASS (8/8 steps). Post-0-9F + post-0-9I path coverage includes `scripts/governance/**` and `docs/recovery/**` and `.github/workflows/**`.

## 11. Gate-B result

_Filled post-PR-open_. Expected: triggered on pull_request + PASS with noop-success (PR touches no `zangetsu/src/modules/**` or `zangetsu/module_contracts/**`).

## 12. Branch protection

Confirmed at:

- `enforce_admins=true` ✅
- `required_signatures=true` ✅
- `linear_history=true` ✅
- `force_push=false` ✅
- `deletions=false` ✅

## 13. Forbidden changes audit

- **No alpha formula/generation change**: ✅ (no `zangetsu/engine/**` or `arena_pipeline.py` or `zangetsu/services/arena*.py` touched)
- **No threshold change**: ✅ (no `zangetsu/config/settings.py` or arena_gates.py threshold constants touched)
- **No Arena pass/fail behavior change**: ✅ (no `arena_pipeline.py` or `arena23_orchestrator.py` or `arena45_orchestrator.py` touched)
- **No champion promotion change**: ✅
- **No execution/capital/risk change**: ✅
- **No CANARY started**: ✅
- **No production rollout started**: ✅

## 14. Remaining risks

1. **Trust-but-verify enforcement**. The tool's `--authorize-trace-only` flag is a declarative assertion by the order writer; the tool does not inspect the actual source code to verify the change is strictly trace-only. Mitigation: behavior-invariance tests + Gate-A + Gate-B + signed PR review collectively catch mis-asserted authorizations.
2. **CODE_FROZEN field catalog may not cover all runtime files**. Only the fields currently in `CODE_FROZEN` (arena_pipeline, arena23_orchestrator, arena45_orchestrator, zangetsu_settings, calcifer_supervisor, zangetsu_outcome) are SHA-tracked. Any new runtime file added in a future module would need to be added to the catalog. Mitigation: `capture_snapshot.sh` snapshot expansion is a separate governance step and is subject to its own order.
3. **No change to runtime enforcement of threshold constants**. 0-9M only changes the DIFF classifier; it does not add runtime tests that enforce threshold values. The existing `test_arena_gates_thresholds_still_pinned_under_p7_pr3` test + future behavior-invariance tests continue to serve as the runtime guard.

## 15. Recommended next action

Primary candidates (j13 to choose):

1. **TEAM ORDER 0-9N — ZANGETSU Deep Optimization Program**. Full system cartography + architecture redesign before any alpha-logic change. Produces roadmap for 0-9O (feedback-guided search), 0-9P (formula intelligence), 0-9Q (arena/deployment hardening), 0-9R (sparse-candidate strategy).
2. **P7-PR4 — A2 trace-native emission in `arena23_orchestrator.py`**. Same pattern as P7-PR3 A1 emission. Under 0-9M, this will automatically classify as `EXPLAINED_TRACE_ONLY` when the PR passes `--authorize-trace-only config.arena23_orchestrator_sha` — NO per-PR exception record needed.
3. **P7-PR3 CANARY activation**. Bounded production-adjacent observation of the A1 trace emission under a future Arena unfreeze order. Currently Arena is frozen; CANARY requires Arena to run.
4. **Sparse-candidate strategy work**. The dominant Arena 2 rejection cause (SIGNAL_TOO_SPARSE, 88.2 %) is a strategy-layer decision: lower `A2_MIN_TRADES`, improve A1 candidate generation, broaden signal windows, or accept status quo. All require separate explicit authorization.

## 16. STOP

No 0-9M STOP condition triggered. Acceptance criteria 1-18 all met. Merge proceeds iff Gate-A + Gate-B both trigger + pass on the evidence PR.

After merge + sync, awaiting j13 next-order decision.
