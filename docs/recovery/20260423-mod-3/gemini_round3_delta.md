# Gemini Round-3 Delta — MOD-3 Phase 4c

**Order**: `/home/j13/claude-inbox/0-4` Phase 4 deliverable
**Produced**: 2026-04-23T08:30Z
**Purpose**: Translate round-3 findings into actionable amendments for MOD-4.

---

## 1. Summary — what MOD-4 must address

| Finding | Severity | Action |
|---|---|---|
| R3b-F1 | **CRITICAL** | Promote `gate_calcifer_bridge` to 10th mandatory OR fold into M8 gate_contract |
| R3a-F8 | HIGH | Activate GitHub branch-protection `required_signatures=true` on main NOW (not Phase 7) |
| R3b-F2 | HIGH | Fix M9 rate_limit semantics — distinguish in-process cache lookup vs REST fetch; REST should be <10/s |
| R3a-F6 | MEDIUM | Add concrete Field 15 runtime enforcement plan (iptables or seccomp-bpf) for Phase 7 |
| R3a-F7 | MEDIUM | Strengthen responsibility→fixture 1:1 check to validate content (AST + min LOC), not just filename |
| R3a-F9 | MEDIUM | Expand Gate-B path triggers to `zangetsu/src/**` OR define explicit allowlist for non-gated paths |
| R3b-F3 | MEDIUM | Add "lean-rollback mode" for M6 with degraded accuracy; mandate snapshot presence |
| R3b-F4 | LOW INCONCLUSIVE | Add local loopback ports to M8 Field 15 egress if IPC used |

4 PARTIAL round-2 findings also need closure in MOD-4:
- R1a-F3 (quiescence loophole) — re-evaluate after 2026-04-30 passes
- R1a-F5 (GPG enforcement) — covered by R3a-F8
- R1b-F1 (Field 15 runtime) — covered by R3a-F6
- R1b-F3 (fixture fluff) — covered by R3a-F7
- R2-F4 (M6 rollback) — covered by R3b-F3

Effective MOD-4 Phase 1 scope: resolve **1 CRITICAL + 2 HIGH + ~4 MEDIUM** findings.

## 2. R3b-F1 CRITICAL — two resolution options

### Option A: Promote `gate_calcifer_bridge` to 10th mandatory module

Similar treatment as `cp_worker_bridge` M9 in MOD-3.

**Pros**:
- Mirrors the "everything the kernel depends on is mandatory" design rule
- Explicit contract + Gemini review + registry entry

**Cons**:
- Inflates mandatory set to 10 modules
- gate_calcifer_bridge is trivial (reads a JSON file, publishes events) — does it deserve module status?

### Option B: Fold `gate_calcifer_bridge` into M8 `gate_contract`

Remove as separate sub-module; M8 reads `/tmp/calcifer_deploy_block.json` directly as part of its gate-decision logic.

**Pros**:
- No mandatory set inflation
- Simpler — gate decisions naturally depend on Calcifer state; the bridge was arbitrary separation
- M8 already owns all gate-decision logic; Calcifer check fits

**Cons**:
- M8 gains a filesystem dep (Field 15 `filesystem_write_paths` needs `/tmp/calcifer_deploy_block.json` READ)
- M8 becomes time-coupled to Calcifer refresh cadence (5min)

**Recommended**: Option B (fold). Simpler, architecturally cleaner. MOD-4 spec update:
- M8 `execution_environment.filesystem_write_paths: []` (unchanged — writes nothing)
- Add M8 `execution_environment.filesystem_read_paths: ["/tmp/calcifer_deploy_block.json"]` (new schema)
- M8 `inputs`: change `CalciferBlockState (from gate_calcifer_bridge)` to `CalciferBlockState (from file read)`
- M8 `failure_surface`: add `{name: calcifer_flag_missing_or_stale, detection: file mtime > 10min OR parse fail, recovery: treat as RED (fail-closed)}`

## 3. R3a-F8 HIGH — GPG activation

Execute immediately (not deferred):

```bash
gh api repos/M116cj/j13-ops/branches/main/protection -X PUT \
  --field required_status_checks[strict]=true \
  --field required_status_checks[contexts][]="build" \
  --field enforce_admins=false \
  --field required_signatures=true \
  --field required_linear_history=true
```

Gate: j13 must have a GPG key configured on GitHub (`gh auth status` verifies). If not, MOD-4 first registers one.

## 4. R3b-F2 HIGH — M9 rate_limit clarification

Current:
```yaml
rate_limit:
  max_events_per_second: 500
  max_events_per_minute: 10000
  burst_size: 1000
  backpressure_policy: drop_newest
```

MOD-4 amended:
```yaml
rate_limit:
  # IN-PROCESS cache lookups (pure memory access)
  cache_lookup_max_per_second: 10000  # essentially unbounded
  # REST fetches to cp_api (loopback HTTP)
  rest_fetch_max_per_second: 10       # per-worker cap; refetch only on TTL expiry or subscribe-push
  # Subscribe event consumption
  subscribe_event_max_per_second: 100  # pg_notify / Redis push
  # Backpressure
  backpressure_policy: drop_newest (for REST) / block_producer (for subscribe)
```

Rationale: rate_limit was conflating three distinct channels. Split clarifies contract.

## 5. R3a-F9 MEDIUM — path triggers expansion

Current:
```
paths:
  - 'zangetsu/src/modules/**'
  - 'zangetsu/src/l[0-9]*/**'
  - 'zangetsu/module_contracts/*.yaml'
  - 'zangetsu/module_contracts/*.yml'
```

MOD-4 amended:
```
paths:
  - 'zangetsu/src/**'        # catches utils/, infra/, etc.
  - 'zangetsu/module_contracts/**'
paths-ignore:
  - 'zangetsu/src/**/test_*.py'   # test files don't trigger gate
  - 'zangetsu/src/**/*.md'        # docs don't trigger gate
```

Plus: add a CI lint step that rejects PRs introducing new top-level `zangetsu/src/<newdir>/` directories without ADR.

## 6. R3a-F7 MEDIUM — fixture content validation

Current: `validate_module_contract.py` just checks filename presence.

MOD-4 amended: add AST check:
```python
import ast
def validate_fixture(fixture_path, responsibility_text):
    tree = ast.parse(open(fixture_path).read())
    # require at least 1 test function
    test_fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    if not test_fns:
        raise ValueError(f"{fixture_path}: no test_* function")
    # require at least 5 non-blank non-pass lines total
    lines = [l for l in open(fixture_path) if l.strip() and l.strip() != 'pass']
    if len(lines) < 5:
        raise ValueError(f"{fixture_path}: {len(lines)} substantive lines < 5 minimum")
```

## 7. R3b-F3 MEDIUM — M6 lean-rollback mode

Amended M6 rollback_surface:
```yaml
rollback_surface:
  code_rollback: git-revert
  state_rollback:
    modes:
      - name: "full"
        precondition: "snapshot present AND < 2h old"
        downstream_effect: "gates pause during restart"
        p50: 90s
        p95: 3min
      - name: "lean"  # NEW
        precondition: "snapshot missing OR > 2h old"
        downstream_effect: "evaluators run with REDUCED data_cache (5 most recent symbols only); gate_contract receives degraded_quality=true flag on each MetricsContract"
        p50: 45s
        p95: 90s
        alert_level: RED (Telegram)
      - name: "cold"
        precondition: "snapshot unusable"
        downstream_effect: "arena state machine freezes; no evaluations"
        p50: 15min
        p95: 30min
        alert_level: CRITICAL
  rollback_time_estimate_worst_case: 30min (cold mode)
```

Mandate: snapshot cron runs every 1h; gov_reconciler alerts if snapshot > 2h old (prevents cold-mode rollback).

## 8. Quiescence loophole (R1a-F3) — MOD-4 decision point

After 2026-04-30T00:35:57Z passes, decide:
- Keep current spec ("no `feat(zangetsu/vN)`")
- Tighten to "no non-documentation commits" (stricter)

Decision criteria: retrospectively count non-`feat` commits during current quiescence window:
- `ae738e37 fix(zangetsu/calcifer)` — 2026-04-23 (no signal of risk)
- `80879795 docs(zangetsu/mod-1-...)` — docs (no reset)
- `73aa7eb5 docs(zangetsu/mod-2-...)` — docs
- (MOD-3 commit, pending) — docs

If 0 non-`fix|docs` commits over the window, loophole didn't hurt this round. If MOD-4 tightens spec, quiescence clock restarts.

## 9. Classification impact on Gate-A

Per 0-4 §Phase 5 logic and `gemini_round3_verdict.md §6`:
**Gate-A classification: `BLOCKED_BY_NEW_FINDINGS`**

Path to CLEARED (optimistic):
1. MOD-4 Phase 1: apply R3b-F1 + R3a-F8 + R3b-F2 (1 CRITICAL + 2 HIGH) — ~1 session
2. MOD-4 Phase 2: apply 4 MEDIUM (R3a-F6 / R3a-F7 / R3a-F9 / R3b-F3)
3. Gemini round-4 segmented re-review — target: clean ACCEPT
4. Quiescence continues (clock preserved unless MOD-4 resets via tightening)
5. Gate-A → CLEARED_PENDING_QUIESCENCE → CLEARED at 2026-04-30 (or later if quiescence reset)

Path to CLEARED (pessimistic):
- If MOD-4 round-4 finds MORE new issues, repeat. Empirically: each round closes most of previous + surfaces some new; convergence expected within 2-3 rounds.

## 10. Label per 0-4 rule 10

- §2 fold-vs-promote analysis: **VERIFIED** (design reasoning)
- §3-§7 amendment texts: **PROBABLE** (design-time; VERIFIED when MOD-4 commits)
- §8 quiescence decision: **INCONCLUSIVE** (depends on empirical 2026-04-30 observation)
- §9 path-to-CLEARED: **PROBABLE** (depends on MOD-4 execution quality)
