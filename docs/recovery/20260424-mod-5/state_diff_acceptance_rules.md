# State Diff Acceptance Rules — MOD-5 Phase 2

**Order**: `/home/j13/claude-inbox/0-7` Phase 2 deliverable
**Produced**: 2026-04-24T00:42Z
**Scope**: For each pair of snapshots, define when the diff is ACCEPTED vs REJECTED vs INSUFFICIENT.

---

## 1. Decision tree

```
For each surface field in (post_snapshot.surfaces.X.fieldN - pre_snapshot.surfaces.X.fieldN):

  IF field value unchanged:
    → allowed, requires NO explanation

  ELSE IF field value changed AND diff-doc references this field with:
      - commit SHA that modified it, OR
      - ADR link that authorized it, OR
      - operator command log, OR
      - automated event (e.g., "Calcifer RED rewrite every 5 min")
    → allowed (classification: EXPLAINED DIFF)

  ELSE IF field value changed AND diff-doc does NOT reference this field:
    → REJECTED (classification: FORBIDDEN UNEXPLAINED DIFF)
    → triggers: RED Telegram + violation log + Condition 5 → DISPROVEN

  ELSE IF snapshot SHA manifest differs but no field-level change detectable:
    → INSUFFICIENT (classification: OPAQUE DIFF)
    → requires deeper audit; Condition 5 → INCONCLUSIVE pending audit
```

## 2. Per-surface allowed-change catalog

For each surface, a catalog of expected / allowed changes:

### 2.1 Runtime surface

| Field | Expected to change? | Allowed explanation |
|---|---|---|
| `arena_processes.count` | NO (frozen) | kill/freeze event (0-1 Phase A) — allowed ONLY with ADR |
| `arena_processes.pids` | NO (frozen) | same as above |
| `systemd_units.*.active_since` | YES (on restart) | restart commit in MOD-N + matching trace file |
| `systemd_units.*.main_pid` | YES (on restart) | same |
| `engine_jsonl_mtime_iso` | NO (frozen) | change = arena respawn = RED ALERT |
| `engine_jsonl_size_bytes` | NO (frozen) | same |
| `calcifer_deploy_block_status` | YES (every 5 min) | expected — Calcifer daemon polling |
| `calcifer_deploy_block_ts_iso` | YES (every 5 min) | same |
| `docker_containers.*.uptime_h` | YES (monotonic) | natural clock increment |

### 2.2 Governance surface

| Field | Expected to change? | Allowed explanation |
|---|---|---|
| `branch_protection_main.*` | RARELY | only via explicit `gh api -X PUT protection` commit + ADR; any other change = RED |
| `governance_matrix_latest.live_rules_count` | RARELY | MOD-N commit adding rules; must cite matrix file |
| `akasha_health` | YES | external service status; ok→degraded acceptable on transient (re-probe within 5 min for confirmation) |

### 2.3 Repo surface

| Field | Expected to change? | Allowed explanation |
|---|---|---|
| `main_head_sha` | YES (every MOD-N commit) | commit SHA referenced in diff doc; must match a git log entry |
| `git_status_porcelain_lines` | NO (should be 0 on clean) | non-zero requires explanation (uncommitted work in progress ADR) |
| `last_5_commits` | YES (rolling) | natural commit history |

### 2.4 Config surface

| Field | Expected to change? | Allowed explanation |
|---|---|---|
| `calcifer_deploy_block_file.sha256` | YES | Calcifer writes every 5 min (natural) |
| `calcifer_state_file.sha256` | YES | same |
| `zangetsu_settings_sha` | NO | changing = threshold/config mutation = RED unless Phase 7 migration (MOD-4 spec forbids during current windows) |
| `arena_pipeline_sha` | NO | same |
| `arena23_orchestrator_sha` | NO | same |

### 2.5 Gate state surface

| Field | Expected to change? | Allowed explanation |
|---|---|---|
| `gate_a_classification` | YES (per MOD-N memo) | matches `gate_a_post_mod*_memo.md` at referenced SHA |
| `cqg_conditions.*` | YES | per classification memo derivation |
| `latest_gemini_round` | YES (monotonic) | Gemini round N → N+1 per MOD-N Phase 4 / 5 |
| `latest_gemini_verdict` | YES | per round output |

## 3. Diff doc requirements

Every diff doc (`docs/governance/diffs/<ts>-<scope>.md`) MUST include:

```
## Pre snapshot
- path: docs/governance/snapshots/<ts_pre>-...json
- sha256_manifest: <hex>

## Post snapshot
- path: docs/governance/snapshots/<ts_post>-...json
- sha256_manifest: <hex>

## Changed fields (with explanation)

### <surface>.<field>
- Pre value: <value>
- Post value: <value>
- Change reason: <commit SHA, ADR link, or operator command>
- Classification: EXPLAINED DIFF

(repeat per changed field)

## Unchanged fields (count)
Total: <int> fields unchanged across 5 surfaces

## Forbidden findings
(none OR list)

## Classification
Explained / Zero / Forbidden / Opaque

## Actor
<who ran the diff analysis>
```

## 4. Forbidden patterns

ANY of the following is an automatic REJECT + RED Telegram:

| Pattern | Classification |
|---|---|
| Arena process count goes from 0 → nonzero without kill-reversal ADR | FORBIDDEN (arena respawn) |
| Any `zangetsu/services/*.py` SHA change without matching commit | FORBIDDEN (threshold/gate drift) |
| `branch_protection_main.required_signatures` transitions true → false without ADR | FORBIDDEN (governance regression) |
| `calcifer_deploy_block_status` transitions RED → GREEN without `deployable_count > 0` in VIEW | FORBIDDEN (fake GREEN) |
| `git_status_porcelain_lines` remains > 0 across a MOD-N commit close | FORBIDDEN (uncommitted drift) |
| Any config surface SHA change without matching commit touching that file path | FORBIDDEN |

## 5. Gemini-reviewable

Every diff doc should be submittable to Gemini as-is for adversarial check: "Is any change here forbidden?" Gemini returns pattern-matched verdict.

This is part of Phase 7 gov_reconciler; for MOD-5 window, manual submission is acceptable.

## 6. Relationship to Condition 5 states

| Diff acceptance result | Condition 5 state |
|---|---|
| Zero diff | VERIFIED (if freshness OK) |
| All explained | VERIFIED (if freshness OK) |
| ≥1 forbidden | DISPROVEN (Condition 5 fails) |
| ≥1 opaque | INCONCLUSIVE (pending audit) |
| No snapshot pair within freshness window | INCONCLUSIVE |

## 7. MOD-5 window exception

During MOD-5 execution itself:
- Pre-snapshot captured at MOD-5 start
- Post-snapshot captured just before commit
- Diff doc explains each change (all map to MOD-5 Phase deliverables + commit)
- Classification: EXPLAINED

This worked example in `controlled_diff_example_current_state.md`.

## 8. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent mutation | ✅ — forbidden patterns §4 catches |
| 3. No live gate change | ✅ — branch protection transitions explicitly gated |
| 8. No broad refactor | ✅ — rules only |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — decision tree §1 covers all classifications |
| Silent failure | PASS — §4 forbidden patterns catch drift |
| External dep | PASS — each pattern has probe path |
| Concurrency | PASS — snapshots are atomic per surface |
| Scope creep | PASS — rules only |

## 10. Label per 0-7 rule 10

- §1 decision tree: **VERIFIED** (deterministic)
- §2 allowed changes: **VERIFIED** (per-surface catalog)
- §4 forbidden patterns: **VERIFIED** (each has specific detector)
- §6 Condition 5 mapping: **VERIFIED** (per CQG §2)
