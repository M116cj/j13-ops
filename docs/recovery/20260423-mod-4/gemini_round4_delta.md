# Gemini Round-4 Delta — MOD-4 Phase 5c

**Order**: `/home/j13/claude-inbox/0-5` Phase 5 deliverable
**Produced**: 2026-04-23T10:55Z
**Purpose**: Round-4 findings translated into MOD-5 amendment targets.

---

## 1. Summary — what MOD-5 must address

| Finding | Severity | MOD-5 action |
|---|---|---|
| R4b-F1 | HIGH | Transition `enforce_admins=true` before Phase 7 entry; PR-based human-signed merges for MOD-5+ |
| R4a-F1 | MEDIUM | Promote L3 `data_provider` to M10 OR ship mock/adapter for isolation |
| R4b-F2 | MEDIUM | M9 `cache_lookup` hard cap + circuit breaker |
| R4b-F3 | MEDIUM | M9 jitter + single_flight mandatory (not "design intent") |
| R4a-F2 | LOW | Build-time egress aggregation tool |
| R4c-F1 | LOW | Gate-B CI BYPASS_WARNING log on admin-signed merges |

## 2. Amendment text — R4b-F1 HIGH (admin bypass)

Target: `amended_modularization_execution_gate_v3.md §5.4`

Addition to §5.4 (required in MOD-5):
```
Phase 7 entry requires `enforce_admins=true` on main branch protection. The MOD-4
bootstrap window operated under `enforce_admins=false` to enable the bootstrap commit itself.
Before any Phase 7 migration PR is merged:
  1. gh api -X PUT /repos/M116cj/j13-ops/branches/main/protection --field enforce_admins=true
  2. verify j13 has GPG key registered on GitHub account
  3. all subsequent commits to main MUST be GPG-signed (no admin bypass)
  4. emergency bypass requires j13 Telegram `/unblock-admin-bypass` + temporary
     enforce_admins=false window, logged in audit
```

## 3. Amendment text — R4a-F1 MEDIUM (L3 data_provider)

Target: `amended_mandatory_module_set_v2.md §5` (now v3 pending MOD-5)

**Decision option A** (PROMOTE — mirrors M9 precedent):
- Promote L3 `data_provider` to mandatory M10
- Add full 15-field contract
- Mandatory set becomes 10

**Decision option B** (MOCK — minimal addition):
- Keep mandatory at 9
- Require Phase 7 to ship `data_provider_mock` for isolation testing
- Add clarifying note in boundary map: "L3 data_provider is REQUIRED at runtime but tested via mock for mandatory-set isolation"

Recommended: Option A (simpler invariant; all mandatory-path deps are mandatory). MOD-5 decides.

## 4. Amendment text — R4b-F2 MEDIUM (cache_lookup hard cap)

Target: `amended_cp_worker_bridge_contract.md §1 outputs.rate_limit.cache_lookup`

Change:
```yaml
cache_lookup:
  max_events_per_second: 20000     # was 10000
  burst_size: 100000               # was 50000
  backpressure_policy: circuit_breaker (open for 1s if sustained breach)  # was not_applicable
  enforcement: hard_client_side    # was soft_metric_only
```

## 5. Amendment text — R4b-F3 MEDIUM (thundering herd mandatory)

Target: `cp_worker_bridge_rate_limit_split.md §6.3`

Move from "design intent" to "mandatory functional requirement":
```
M9 MUST implement:
- single_flight coalesce: if worker A is mid-fetch on key K, worker B's rest_fetch
  piggybacks on A's pending request. Required for Phase 7 acceptance.
- jitter: all workers add random 0-500ms delay before post-invalidation refetch.
  Required for Phase 7 acceptance.

Gate-B.B.1 validation: `validate_module_contract.py` asserts both features
declared in contract AND implemented per `channel_tests/test_thundering_herd.py`
golden fixture.
```

## 6. Amendment text — R4a-F2 LOW (build-time egress aggregation)

Target: `amended_module_contract_template_v3.md §2.1` transitive-egress rule

Additive amendment (MOD-5):
```
Build-time tooling (MOD-5 deliverable): `aggregate_egress.py` walks every module's
declared permitted_egress_hosts + each import's library contract. Produces a
per-module "effective egress" manifest used for:
  - runtime enforcement policy generation (iptables / seccomp rules)
  - audit-log verification
  - operator review at module deployment time
```

## 7. Amendment text — R4c-F1 LOW (BYPASS_WARNING log)

Target: `github_actions_gate_b_enforcement_spec.md §2`

Add to workflow:
```yaml
- name: Detect admin-bypass + emit BYPASS_WARNING
  run: |
    # Check if commit is signed
    SIG=$(gh api /repos/M116cj/j13-ops/commits/${{ github.sha }} --jq .commit.verification.verified)
    if [ "$SIG" != "true" ]; then
      echo "::warning::BYPASS_WARNING: Commit ${{ github.sha }} is unsigned (admin-bypass active)"
      # Also post a PR comment if in PR context
      if [ -n "${{ github.event.pull_request.number }}" ]; then
        gh pr comment ${{ github.event.pull_request.number }} --body "⚠️ **BYPASS_WARNING**: This commit is unsigned. Admin-bypass via \`enforce_admins=false\` was used. Phase 7 requires \`enforce_admins=true\` with human-signed merges."
      fi
    fi
```

## 8. MOD-5 scope suggestion

MOD-5 Team Order (if j13 chooses to issue) should have these Phase targets:
- **Phase 1 HIGH**: R4b-F1 (enforce_admins transition + PR-based workflow)
- **Phase 2 MEDIUM**: R4a-F1 + R4b-F2 + R4b-F3 (data_provider decision + cache hard cap + thundering-herd mandate)
- **Phase 3 LOW**: R4a-F2 + R4c-F1
- **Phase 4 Gemini round-5** verification
- **Phase 5 Gate-A post-MOD-5 reassessment** (target: CLEARED or CLEARED_PENDING_CONDITIONS under 0-6 policy)

## 9. Relationship to 0-6 governance patch

Per 0-6 `/home/j13/claude-inbox/0-6`, time-locks are removed post-MOD-4. Gate-A will be re-assessed under the 6 Condition Groups (Runtime Freeze / Governance Live / Corpus Consistency / Adversarial Closure / Controlled-Diff / Rollback Readiness).

Under the new rules, R4b-F1 + R4a-F1 + R4b-F2 + R4b-F3 together violate **Condition 4: Adversarial Closure Proof** ("no blocking HIGH findings remain"). Therefore post-0-6:
- Old classification: CLEARED_PENDING_QUIESCENCE
- 0-6-era classification: **STILL_PARTIALLY_BLOCKED** (pending Condition 4 via MOD-5 resolution)

0-6 governance patch will document this reclassification (the r4b_F1 remediation becomes the new Condition-4 unblock path rather than a date-based unlock).

## 10. Non-negotiable rules compliance

| Rule | Compliance |
|---|---|
| 5. No Phase 7 migration work | ✅ — amendments scheduled for MOD-5 |
| 10. Labels | ✅ |

## 11. Label per 0-5 rule 10

- §2-§7 amendment texts: **PROBABLE** (design-time; VERIFIED when MOD-5 lands)
- §8 MOD-5 scope: **PROBABLE** (j13 discretion)
- §9 0-6 reclassification: **VERIFIED** (per 0-6 §C Condition 4 + §D allowed states)
