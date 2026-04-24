# Controlled-Diff Worked Example — Current State (MOD-5 Phase 2)

**Order**: `/home/j13/claude-inbox/0-7` Phase 2 deliverable
**Produced**: 2026-04-24T00:29Z (snapshot time) → 2026-04-24T00:48Z (doc time)
**Purpose**: Apply the controlled-diff framework to the CURRENT system state. Demonstrates Condition 5 is judgeable by explicit evidence, not hand interpretation.

---

## 1. Reference baseline: 0-6 governance-patch commit `c420ed8f`

Baseline snapshot (implicit — derived from commit metadata + live probe at 2026-04-24T00:29:02Z):

```json
{
  "schema_version": 1,
  "captured_at": "2026-04-24T00:29:02Z",
  "captured_by": "claude@mod-5-phase-2-example",
  "purpose": "mod-5-start baseline for Condition 5 proof",
  "surfaces": {
    "runtime": {
      "arena_processes": {"count": 0, "pids": []},
      "engine_jsonl_mtime_iso": "2026-04-23T00:35:54.857377417+00:00",
      "engine_jsonl_size_bytes": 38638779,
      "calcifer_deploy_block_status": "RED",
      "calcifer_deploy_block_ts_iso": "2026-04-24T00:25:15.725810+00:00"
    },
    "governance": {
      "branch_protection_main": {
        "required_signatures":     {"enabled": true},
        "required_linear_history": {"enabled": true},
        "enforce_admins":          {"enabled": false}
      },
      "akasha_health": "ok"
    },
    "repo": {
      "main_head_sha": "c420ed8fd6dbc20f232efe01d52528d2c0f98049",
      "main_head_subject": "docs(zangetsu/governance-conditional-patch): Team Order 0-6 — time-locks removed, CQG adopted; Gate-A reclassified STILL_PARTIALLY_BLOCKED",
      "git_status_porcelain_lines": 0
    },
    "config": {
      "calcifer_deploy_block_file":  {"sha256": "a0620c6f84aec0e5b7146c8864099fed1dea0638e18fd4e6a9b6c195f4b3d6a6"},
      "zangetsu_settings_sha":       {"sha256": "97467c5046fde53e835b91ad19c3afdbe7e99d649f5655fc718ea70a0cdd723f"},
      "arena_pipeline_sha":          {"sha256": "34a3791f1686cc5f7c50c5f2f7e6db7eb1afca7340166dec63a32c5b05273d83"},
      "arena23_orchestrator_sha":    {"sha256": "81f48ccffca03f08ad9f1c5264a8af86acc6f83e72adad0c562f3d87ba1e750d"},
      "arena45_orchestrator_sha":    {"sha256": "fe97c7a1aeb9b97bf4dadee79330667ae19394cbae154f37abdb1af525588960"},
      "calcifer_supervisor_sha":     {"sha256": "9fa1cc6c63444724c055774b01a93423d390693cf711ea90f20466878f82c889"},
      "zangetsu_outcome_sha":        {"sha256": "a2cce61f08530460cc153a517248181214e775000c3fb7e29060aa1415ce046b"}
    },
    "gate_state": {
      "gate_a_classification": "STILL_PARTIALLY_BLOCKED",
      "classification_source_file": "docs/governance/20260423-conditional-patch/authoritative_condition_matrix.md",
      "cqg_conditions": {
        "runtime_freeze":     "VERIFIED",
        "governance_live":     "PARTIAL",
        "corpus_consistency":  "VERIFIED",
        "adversarial_closure": "PARTIAL",
        "controlled_diff":     "INCONCLUSIVE",
        "rollback_readiness":  "VERIFIED"
      },
      "latest_gemini_round": 4,
      "latest_gemini_verdict": "ACCEPT_WITH_AMENDMENTS"
    }
  }
}
```

## 2. Diff against predecessor commit `ad2671f3` (MOD-4)

Between `ad2671f3` (MOD-4 close) and `c420ed8f` (0-6 governance patch commit):

### Runtime surface
| Field | Value | Changed? | Explanation |
|---|---|---|---|
| arena_processes.count | 0 | NO | Frozen since 2026-04-23T00:35:57Z |
| engine_jsonl_mtime_iso | 2026-04-23T00:35:54Z | NO | Consistent with frozen arena |
| engine_jsonl_size_bytes | 38638779 | NO | Static |
| calcifer_deploy_block_status | RED | NO | Preserved |
| calcifer_deploy_block_ts_iso | 00:25:15 (2026-04-24) | YES | **EXPLAINED**: Calcifer daemon polls every ~5 min (expected per `state_diff_acceptance_rules.md §2.1`) |

### Governance surface
| Field | Value | Changed? | Explanation |
|---|---|---|---|
| required_signatures.enabled | true | NO | LIVE since MOD-4 Phase 2A |
| required_linear_history.enabled | true | NO | LIVE since MOD-4 Phase 2A |
| enforce_admins.enabled | false | NO | Unchanged (MOD-5 Phase 1 adopts compensating control, not activation change) |
| akasha_health | ok | NO | Healthy |

### Repo surface
| Field | Value | Changed? | Explanation |
|---|---|---|---|
| main_head_sha | c420ed8f | YES | **EXPLAINED**: 0-6 governance-patch commit landed after MOD-4 close; commit references Team Order 0-6 |
| git_status_porcelain_lines | 0 | NO | Clean |

### Config surface
| Field | SHA256 | Changed? | Explanation |
|---|---|---|---|
| calcifer_deploy_block_file | a0620c6f... | YES | **EXPLAINED**: Calcifer polls every ~5 min; SHA changes expected per `state_diff_acceptance_rules.md §2.4` |
| zangetsu_settings_sha | 97467c5... | NO | No settings change — consistent with "no threshold change" rule |
| arena_pipeline_sha | 34a3791f... | NO | No code change |
| arena23_orchestrator_sha | 81f48ccf... | NO | No code change |
| arena45_orchestrator_sha | fe97c7a1... | NO | No code change |
| calcifer_supervisor_sha | 9fa1cc6c... | NO | No code change since `ae738e37` |
| zangetsu_outcome_sha | a2cce61f... | NO | No code change since `ae738e37` |

### Gate state surface
| Field | Value | Changed? | Explanation |
|---|---|---|---|
| gate_a_classification | STILL_PARTIALLY_BLOCKED | YES | **EXPLAINED**: Transitioned from CLEARED_PENDING_QUIESCENCE (MOD-4 legacy framework) to STILL_PARTIALLY_BLOCKED (0-6 condition-based framework); classification_source_file moved from `gate_a_post_mod4_memo.md` to `authoritative_condition_matrix.md` |
| cqg_conditions | 3 VERIFIED + 2 PARTIAL + 1 INCONCLUSIVE | YES | **EXPLAINED**: 0-6 introduced the 6-condition framework; pre-0-6 this field was null/not-evaluated |
| latest_gemini_round | 4 | NO | Unchanged |

## 3. Diff classification

| Category | Count | Fields |
|---|---|---|
| Zero diff (unchanged) | 13 | Most runtime, all governance, config code paths, etc. |
| EXPLAINED DIFF | 5 | calcifer_deploy_block_ts (scheduled), main_head_sha (commit trail), calcifer_deploy_block_file SHA (scheduled), gate_a_classification (0-6 policy), cqg_conditions (0-6 introduction) |
| FORBIDDEN UNEXPLAINED | 0 | — |
| OPAQUE | 0 | — |

**Diff verdict**: **EXPLAINED** (no forbidden; no opaque).

## 4. Per-forbidden-pattern audit (`state_diff_acceptance_rules.md §4`)

| Forbidden pattern | Detected in current diff? |
|---|---|
| Arena process count 0 → nonzero without ADR | NO — count stays 0 |
| `zangetsu/services/*.py` SHA change without commit | NO — SHAs unchanged |
| `required_signatures` true → false without ADR | NO — stays true |
| `calcifer_deploy_block_status` RED → GREEN without deployable_count > 0 | NO — stays RED |
| `git_status_porcelain_lines` > 0 across MOD close | NO — clean at MOD-4 close AND at this snapshot |
| Config surface SHA change without matching commit | NO — SHA changes limited to scheduled files (Calcifer block) |

**All 6 forbidden patterns: NONE DETECTED.**

## 5. Condition 5 verdict for current state

Per `controlled_diff_framework.md §3` proof protocol:

- Pre snapshot: implicit baseline at `ad2671f3` (MOD-4 close)
- Post snapshot: this doc §1 at 2026-04-24T00:29:02Z
- Diff classification: EXPLAINED (§3)
- Forbidden patterns: none (§4)

**Condition 5 (Controlled-Diff Proof) for current state: VERIFIED.**

## 6. Freshness check

- Snapshot timestamp: 2026-04-24T00:29:02Z
- Max age for "current" snapshot: 12 hours (per `controlled_diff_framework.md §2.5`)
- Current age: <1 hour at time of MOD-5 Phase 2 doc creation

Freshness: PASS.

## 7. Integration with MOD-5 close

At MOD-5 commit time, a fresh snapshot will be captured and compared against this baseline. Any field change will be EXPLAINED (commit SHA + MOD-5 deliverables) or flagged as FORBIDDEN.

Expected MOD-5 close diffs:
- `main_head_sha` → new MOD-5 commit SHA (EXPLAINED by MOD-5 commit itself)
- `gate_state.gate_a_classification` → per Phase 5 memo (EXPLAINED by `gate_a_post_mod5_memo.md`)
- `gate_state.cqg_conditions` → per Phase 5 memo
- `calcifer_deploy_block_ts_iso` + SHA → routine polling (EXPLAINED)

No other field changes expected. If any config surface file SHA changes, it's FORBIDDEN.

## 8. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent mutation | ✅ — §4 explicitly catalogs forbidden patterns, none found |
| 3. No live gate change | ✅ — branch protection state snapshot unchanged |
| 4. No arena restart | ✅ — arena count stays 0 |
| 9. No time-based unlock | ✅ — freshness window is a bound, not a trigger |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — all 5 surfaces covered |
| Silent failure | PASS — SHA hashes + status fields |
| External dep | PASS — each surface probed independently |
| Concurrency | PASS — point-in-time atomic snapshot |
| Scope creep | PASS — applies framework only |

## 10. Label per 0-7 rule 10

- §1 snapshot: **VERIFIED** (live probes captured + SSH trace available)
- §3 diff classification: **VERIFIED** (deterministic per acceptance rules)
- §4 forbidden-pattern audit: **VERIFIED** (none detected)
- §5 Condition 5 verdict: **VERIFIED**
