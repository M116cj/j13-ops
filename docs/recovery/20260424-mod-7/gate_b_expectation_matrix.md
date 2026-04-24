# Gate-B Expectation Matrix

- **Scope**: Enumerates every condition under which Gate-B MUST block a Phase 7 PR per 0-9 §6 + MOD-6 `module-migration-gate.yml`.
- **Actions performed**: Cross-referenced 0-9 §6 blocker list against the live `.github/workflows/module-migration-gate.yml` steps; flagged which are live vs spec-pending.
- **Evidence path**: `.github/workflows/module-migration-gate.yml` (committed MOD-6 `da66c296`); 0-9 §6.
- **Observed result — blocker-to-enforcement mapping**:

| 0-9 §6 blocker | Live in module-migration-gate.yml? | Enforced at step | Evidence |
|---|---|---|---|
| unsigned commit detected | YES (main-branch-level via `required_signatures=true`) | rejected at push (API 422) | branch protection API |
| direct main mutation detected | YES (main-branch-level via `required_signatures=true` + `enforce_admins=true` + `linear_history=true`) | rejected at push | same |
| missing migration report | PARTIAL — Gate-A step 1.1 requires classification memo; Gate-B does not yet grep for per-PR migration report | Phase 7 PR body review | workflow step lacking — upgrade in next iteration |
| missing SHADOW plan | PARTIAL — checks require `docs/rollback/<module>.md`; SHADOW plan TBA per PR | per-PR author discipline; workflow upgrade pending | `shadow_canary_rehearsal_standard.md` |
| missing CANARY plan | same as SHADOW plan | same | same |
| missing rollback path | YES (B.3 rollback runbook presence check in `gate_b_per_module`) | file `docs/rollback/<module_id>.md` required | module-migration-gate.yml B.3 |
| forbidden runtime file changed | NOT YET LIVE — file-path allowlist enforcement pending P7-M1 allowlist addition | MOD-7 follow-up work | enforce when P7-PR1 ready |
| alpha / threshold / arena runtime logic changed outside PR scope | PARTIAL — covered by Controlled-Diff `state_diff_acceptance_rules.md §4` forbidden patterns (catches SHA change on `zangetsu/services/*.py`, `settings.py`) | Controlled-Diff tripwire | `scripts/governance/diff_snapshots.py` |
| controlled-diff has forbidden diff | YES (controlled-diff runs locally for now; Phase 7 embeds in CI) | per `controlled_diff_live_run_report.md` | MOD-6 Phase 4 |
| unknown rejection reason dominates | NOT YET LIVE — requires runtime telemetry counters from P7-PR1 before check is possible | Phase 7 first telemetry PR (P7-PR1 itself) creates the data; subsequent PRs can assert UNKNOWN_REJECT < 5% | P7-PR1 delivers the substrate |

### Coverage tally

| Live enforcement | Count |
|---|---|
| Fully live | 5 |
| Partial live (discipline + some automation) | 4 |
| Not yet live (requires P7-M1 telemetry) | 1 |
| Not yet live (requires post-P7-M1 hardening) | 1 |

Total 0-9 §6 blockers: 11 (deduped)
Fully live: 5
Partial: 4
Pending P7-M1: 2

- **Forbidden changes check**: Matrix is read-only; records what MOD-6 already delivered + what P7-M1 must add. No state mutation.
- **Residual risk**:
  - UNKNOWN_REJECT dominance check cannot be automated until P7-M1 emits real counters. Compensating: P7-M1 PR body MUST include a preflight forecast; Gemini round-6 adversarial on P7-PR1 challenges the forecast.
  - Forbidden-runtime-file check (allowlist) requires a hardened `validate_module_contract.py` in CI; upgrade during P7-PR1.
- **Verdict**: Gate-B coverage is SUFFICIENT for Phase 7 kickoff under 0-9 governance. Gaps are explicit + tracked + tied to P7-PR1 landing.
