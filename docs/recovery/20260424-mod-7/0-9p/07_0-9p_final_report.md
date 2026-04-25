# 0-9P — Generation Profile Passport Persistence and Attribution Closure Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

## 2. Baseline

- origin/main SHA at start: `75f7dd8dc66af6e3c06e7c05ad7c6cffd43a6376`
- branch: `phase-7/0-9p-generation-profile-passport-persistence`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature verification: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`

## 3. Mission

Persist `generation_profile_id` + `generation_profile_fingerprint`
into the candidate passport at A1 admit time so A2/A3 telemetry can
attribute Arena outcomes to the original A1 generation profile.
Metadata-only / attribution-only. Zero behavior change to Arena
gates, thresholds, champion promotion, or deployable_count.

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/arena_pipeline.py` | runtime metadata-only | Adds two fields to `passport.arena1` (try/except wrapped); EXPLAINED_TRACE_ONLY |
| `zangetsu/services/generation_profile_identity.py` | helper extension | New `resolve_attribution_chain` pure-Python helper; testable 4-level precedence contract |
| `zangetsu/tests/test_passport_profile_attribution.py` | new test file | 40 tests |
| `docs/recovery/20260424-mod-7/0-9p/01..07*.md` | evidence docs | 7 markdown artifacts |

## 5. Attribution precedence

```
1. passport.arena1.generation_profile_id           ← 0-9P writes here
2. passport.generation_profile_id                  ← future schema variant
3. orchestrator consumer profile                    ← P7-PR4B fallback
4. UNKNOWN_PROFILE / UNAVAILABLE                    ← final fallback
```

Source label exposed via `resolve_attribution_chain(...).source`:
`passport_arena1` / `passport_root` / `orchestrator` / `fallback`.

## 6. Schema delta

`passport.arena1` gains 2 fields:

```json
"generation_profile_id": "gp_aaaa1111bbbb2222",
"generation_profile_fingerprint": "sha256:..."
```

Both fields always present (UNKNOWN / UNAVAILABLE on resolution
failure). Backward compatible — existing readers ignore unknown
fields; P7-PR4B reader picks them up automatically.

## 7. Behavior invariance

| Item | Status |
| --- | --- |
| No alpha generation change | ✅ |
| No formula generation change | ✅ |
| No mutation / crossover change | ✅ |
| No search policy change | ✅ |
| No generation budget change | ✅ |
| No sampling weights change | ✅ |
| No threshold change (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED, A3 segments) | ✅ |
| No Arena pass/fail change | ✅ |
| No champion promotion change | ✅ |
| No `deployable_count` semantic change | ✅ |
| No execution / capital / risk change | ✅ |
| No CANARY started | ✅ |
| No production rollout started | ✅ |
| No formula lineage introduced | ✅ |
| No parent-child ancestry introduced | ✅ |
| Telemetry-failure not blocking Arena | ✅ |

Detailed: `04_behavior_invariance_audit.md`.

## 8. Test results

```
$ python3 -m pytest zangetsu/tests/test_passport_profile_attribution.py
======================== 40 passed, 1 warning in 0.11s =========================
```

Adjacent suites: 156 PASS / 0 regression. Detailed: `05_test_results.md`.

## 9. Controlled-diff

Expected: **EXPLAINED_TRACE_ONLY**.

```
Zero diff:                   ~42 fields
Explained diff:              1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:   1 field   — config.arena_pipeline_sha
Forbidden diff:              0 fields
```

Authorized via `--authorize-trace-only config.arena_pipeline_sha`.
Other CODE_FROZEN runtime SHAs zero-diff. Detailed:
`06_controlled_diff_report.md`.

## 10. Gate-A / Gate-B / Branch protection

Expected: **PASS / PASS**.
Branch protection unchanged: `enforce_admins=true`,
`required_signatures=true`, `linear_history=true`,
`allow_force_pushes=false`, `allow_deletions=false`.

## 11. Forbidden changes audit

- CANARY: NOT started.
- Production rollout: NOT started.

## 12. Remaining risks

- **Sample-size lag**: existing in-flight champions written to
  `champion_pipeline` before this PR will not have the new passport
  fields. A2/A3 reading those passports will fall back to
  orchestrator consumer profile (precedence level 3). PR-B
  `0-9P-AUDIT` will measure the proportion and classify GREEN /
  YELLOW / RED.
- **Backfill not authorized**: 0-9P does not retroactively rewrite
  existing passports. If j13 wants backfill, that requires a separate
  metadata-migration order (Medium-Risk per governance matrix).
- **Schema evolution**: future passport schema changes must respect
  the 4-level precedence. A future order changing the passport
  structure must include explicit precedence documentation.

## 13. Recommended next action

**PR-B / 0-9P-AUDIT — Profile Attribution Coverage and Replay
Validation.** Build offline audit tool to measure:

- `passport_identity_rate` (= passport.arena1 hits / total).
- `orchestrator_fallback_rate`.
- `unknown_profile_rate`.
- `profile_mismatch_count` (A1 ≠ A2 ≠ A3 attribution).
- `stage_counts_by_profile`.
- Replay-validation correctness.

Verdict GREEN → PR-C / 0-9R-IMPL-DRY 可進入。
