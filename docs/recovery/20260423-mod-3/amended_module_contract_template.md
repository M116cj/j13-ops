# Amended Module Contract Template — MOD-3

**Order**: `/home/j13/claude-inbox/0-4` Phase 2 deliverable
**Produced**: 2026-04-23T07:32Z
**Supersedes**: `docs/recovery/20260423-mod-1/module_contract_template.md` §2 (14 fields) via amendment — adds Field 15 `execution_environment`
**Resolves**: Gemini R1b-F1 HIGH (egress stealth), R1b-F2 MEDIUM (compute budget), R1b-F3 MEDIUM (fluff)

---

## 1. Amendment summary

| Change | Source | Severity |
|---|---|---|
| **Add Field 15 `execution_environment`** (permitted_egress, subprocess, filesystem, rss, cpu caps) | R1b-F1 | HIGH |
| Add `rate_limit` sub-schema to Field 5 (Outputs) | R1b-F2 | MEDIUM |
| Tighten §4 acceptance checklist: responsibilities MUST map 1:1 to test fixtures | R1b-F3 | MEDIUM |
| Cross-reference §8.2 threshold split-brain note | (from r2_recovery_review §8.2) | MEDIUM |

Fields 1–14: unchanged from MOD-1 baseline (Field 1 module_name … Field 14 console_controls).

## 2. Field 15 — `execution_environment` (NEW MANDATORY)

### Purpose

Every module MUST declare what OS-level capabilities it uses. This closes the egress-stealth loophole (R1b-F1): a module declaring `blackbox_allowed: false` cannot quietly call `requests.post("https://external.api/")` — if `permitted_egress_hosts` doesn't list that host, the CI check fails.

### Schema

```yaml
execution_environment:
  # Network egress — empty list = no network calls permitted
  permitted_egress_hosts:
    - "hostname:port"         # or "hostname" for any port
    - "*.domain.tld:443"      # wildcard-subdomain syntax
  # e.g., for data_provider: ["api.binance.com:443", "fapi.binance.com:443"]
  # for gate_contract: [] — pure local compute

  # Subprocess permissions
  subprocess_spawn_allowed: true | false
  subprocess_permitted_binaries:   # only enforced if spawn_allowed == true
    - "/usr/bin/python3"
    - "/usr/bin/docker"

  # Filesystem writes (ABSOLUTE path prefixes)
  filesystem_write_paths:
    - "/var/log/zangetsu/"
    - "/tmp/"                      # ephemeral
  # read access is unrestricted by default (modules may read any file they have OS permissions for)

  # Compute budget (per-module cap)
  max_rss_mb: <int>                # kill if exceeded for 60s
  max_cpu_pct_sustained: <int>     # alert if exceeded for 60s; kill if exceeded for 5min

  # Privileged capabilities (rare; require explicit ADR)
  requires_root: false
  requires_docker_group: false
  requires_sudo: false
```

### Required values per module (MANDATORY — fail B.1 if missing)

Every module YAML MUST populate every sub-field. Empty list (`[]`) is valid for egress; explicit numeric caps required for RSS/CPU.

### Enforcement

| Check location | How enforced |
|---|---|
| Gate-B pre-merge | `validate_module_contract.py` verifies Field 15 schema + required values |
| Runtime | obs_metrics tracks actual RSS/CPU; gov_reconciler compares against declared caps; ALERT on breach |
| Egress runtime | Optional: iptables rules per-process (out of scope for MOD-3; documented as Phase 7 hardening) |
| Subprocess runtime | Optional: seccomp / syscall filter (out of scope) |
| Filesystem runtime | Optional: AppArmor profile per-module (out of scope) |

Mandatory-at-review-time enforcement (the Field 15 declaration itself) is sufficient for MOD-1 acceptance. Runtime enforcement lands in Phase 7.

### Why this closes R1b-F1

Before Field 15:
- `gate_contract` could `import requests; requests.post("https://external-llm-api/")` and silently act as a black-box without declaring it.
- Declaration `blackbox_allowed: false` was not mechanically verifiable.

After Field 15:
- `gate_contract.yaml` has `permitted_egress_hosts: []`.
- If the code calls `requests.post()`, either:
  - Runtime: egress audit catches the connection attempt (gov_reconciler logs + alerts)
  - CI: a static-analysis pass scans source for `requests.post`/`urllib`/etc. and fails if any call's target isn't in the permitted list (Phase 7 CI addition)

Mechanism is verifiable, not honor-system.

## 3. Field 5 (Outputs) — amended sub-schema for `rate_limit` (R1b-F2)

```yaml
outputs:
  - contract_name: <ContractName>
    consumer_modules: [<module_id>, ...]
    cardinality: one_per_input | n_per_input | stream
    guarantees:
      delivery: at_most_once | at_least_once | exactly_once
      ordering: total | partition | none
      idempotency: true | false
    # NEW MOD-3 addition
    rate_limit:
      max_events_per_second: <int>      # 0 = no limit
      max_events_per_minute: <int>
      burst_size: <int>
      backpressure_policy: drop_oldest | drop_newest | block_producer | shed_priority
```

Modules that produce bursty output MUST declare rate_limit or be rejected.

## 4. Field 3 (responsibilities) — tightened §4 acceptance check (R1b-F3)

Old rule (MOD-1):
> `responsibilities` is 2–7 entries; each = verb + noun.

New rule (MOD-3):
- Same syntactic check PLUS
- **Each responsibility MUST map to at least one golden fixture in `test_boundary`**
- Gate-B CI check: `validate_module_contract.py` does 1:1 matching between responsibilities list and filenames under `test_boundary`. Missing coverage = rejection.

Anti-pattern example now rejected:
```yaml
responsibilities:
  - Handle logic        # too vague; no corresponding fixture; REJECTED
  - Route events        # passes only if test_boundary contains `test_route_events.py` or similar
```

## 5. Anti-patterns §5 — amended

Original 9 anti-patterns preserved; added:

| NEW pattern | Why rejected |
|---|---|
| `permitted_egress_hosts` not declared OR contains `"*"` (wildcard-any) | Wildcard egress = no egress control; violates R1b-F1 spirit |
| `max_rss_mb: 0` or missing | Module must have compute budget cap |
| Declaring `subprocess_spawn_allowed: true` without `subprocess_permitted_binaries` list | Unconstrained subprocess = implicit black-box |
| `responsibilities` containing any "and" / "or" / "," inside an entry | Multi-purpose in one entry = not 1 verb + 1 noun |

## 6. Field 10 (rollback) / Field 12 (replacement) redundancy — DISPROVEN

Per Gemini R1b-F4 DISPROVEN: Rollback (Failure-phase) and Replacement (Evolution-phase) serve distinct operational semantics. No change.

## 7. Acceptance checklist (§4 of original template) — amended

All 15 fields required (was 14):
- [ ] Fields 1-14 per MOD-1 baseline
- [ ] **Field 15 execution_environment** populated with:
  - [ ] permitted_egress_hosts list (can be empty)
  - [ ] subprocess_spawn_allowed bool (+ binaries list if true)
  - [ ] filesystem_write_paths list (at least `/tmp/` or justified absence)
  - [ ] max_rss_mb explicit integer
  - [ ] max_cpu_pct_sustained explicit integer
  - [ ] privileged-capability bools all populated
- [ ] responsibilities list maps 1:1 to test_boundary fixtures (R1b-F3)
- [ ] outputs rate_limit sub-schema present if cardinality is `stream` or `n_per_input`

## 8. All 7 existing mandatory module contracts need Field 15

Per amendment, `module_boundary_map.md §MOD-1.B` contracts for:
- engine_kernel
- gate_registry
- obs_metrics
- gov_contract_engine
- search_contract
- eval_contract
- adapter_contract

…each need Field 15 added. Plus the 2 new modules:
- **gate_contract** (Field 15 declared in `gate_contract_module_spec.md §5`)
- **cp_worker_bridge** (Field 15 to be declared in `cp_worker_bridge_promotion_spec.md`)

The bulk Field 15 population for the 7 existing modules is spec-level only in MOD-3 (see `mod1_corpus_consistency_patch.md §Field 15 population`); concrete YAML happens in Phase 7 when `zangetsu/module_contracts/<id>.yaml` files are authored.

## 9. Resolution status

| Finding | Status |
|---|---|
| R1b-F1 HIGH (egress stealth) | **RESOLVED** — Field 15 mandatory |
| R1b-F2 MEDIUM (compute/rate_limit) | **RESOLVED** — rate_limit in Field 5; RSS/CPU in Field 15 |
| R1b-F3 MEDIUM (responsibilities fluff) | **RESOLVED** — 1:1 fixture mapping check |
| R1b-F4 LOW DISPROVEN (rollback vs replacement) | no change (already correct) |

## 10. Label per 0-4 rule 10

- §2 Field 15 schema: **PROBABLE** (design; VERIFIED when first module yaml validates)
- §3 rate_limit: **PROBABLE**
- §4 1:1 fixture mapping: **PROBABLE** (CI-enforceable)
- §7 15-field checklist: **PROBABLE**
- §9 resolution status: **PROBABLE** pending Gemini round-3
