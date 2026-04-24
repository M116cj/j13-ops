# Gate-A Blocker Matrix — MOD-2 Phase 5

**Order**: `/home/j13/claude-inbox/0-3` Phase 5 second deliverable
**Produced**: 2026-04-23T06:05Z
**Scope**: Exact enumeration of what remains between current state and Phase 7 eligibility.

---

## 1. Matrix

| Sub-condition | Blocker | Severity | Type | Remediation | ETA (if defined) |
|---|---|---|---|---|---|
| A.1 | Gemini R1a-F1: Gate-B label-trigger bypass | **CRITICAL** | Architectural amendment (MOD-1 exec_gate §5.2) | Change trigger from label-based to path-based in GitHub Actions workflow; commit to `modularization_execution_gate.md`. Also mirror Gate-A hook into server-side workflow. | MOD-3 Phase 1 |
| A.1 | Gemini R2-F1: Missing `gate_contract` from 7 mandatory modules | **CRITICAL** | Architectural amendment (MOD-1 boundary §MOD-1.B) | Add Module 8 `gate_contract` with full 14-field contract; update README deliverables index to reflect 8 mandatory; update §MOD-1.C mapping. | MOD-3 Phase 1 |
| A.1 | Gemini R1a-F2: Local hook bypass via `--no-verify` | HIGH | Enforcement amendment | Add server-side GitHub Actions workflow that mirrors Gate-A conditions; local hook becomes convenience only. | MOD-3 Phase 1 |
| A.1 | Gemini R1b-F1: blackbox_allowed=false egress stealth | HIGH | Contract schema amendment | Add Field 15 `execution_environment` (permitted_egress_hosts, subprocess_spawn, filesystem_write_paths, max_rss_mb, max_cpu_pct_sustained) to template + 7 existing contracts. | MOD-3 Phase 1 |
| A.1 | Gemini R2-F2: Kernel vs gov split-brain on rollout gating | HIGH | Module boundary amendment | Remove "enforces rollout gating" from engine_kernel responsibilities; add "consumes PolicyVerdict from gov_contract_engine". Add "owns rollout gating" to gov_contract_engine. | MOD-3 Phase 1 |
| A.1 | Gemini R2-F3: `cp_worker_bridge` referenced but not mandatory | HIGH | Module promotion | Promote `cp_worker_bridge` to 9th mandatory module with full contract, OR refactor the 6 inputs that reference it. | MOD-3 Phase 1 |
| A.1 | Gemini R1a-F3: Quiescence only blocks `feat(`, not `fix(` / `refactor(` | MEDIUM | Spec amendment | Change §A.2 from "No `feat(zangetsu/vN)` commits" to "Zero non-documentation commits to `zangetsu/` tree". | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R1a-F4: Rollback p95 unverified | MEDIUM | Validation amendment | Add §B.2 mandatory requirement: empirical rollback p95 measured + logged during SHADOW rehearsal. | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R1a-F5: Override ADR lacks crypto identity | MEDIUM | Enforcement amendment | Require GPG-signed commits for ADRs with `gate-override` tag; update §5 to verify signature against j13 public key. | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R1b-F2: Compute-budget / rate-limit missing | MEDIUM | Contract schema amendment | Merge rate_limit + compute_budget sub-schemas into Field 5 (Outputs). | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R1b-F3: Responsibilities semantic-fluff | MEDIUM | Acceptance check amendment | Require responsibilities 1:1 mapping to test_boundary fixtures. | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R2-F4: M6 eval_contract rollback p95 wishful | MEDIUM | Contract correction | Downgrade p95 to 30min OR add persistent data_cache snapshot requirement in M6. | MOD-3 Phase 1 (soft) |
| A.1 | Gemini R2-F5: M6 missing L9 adapter disclaimer | LOW | Doc consistency | Add same clause as M5 search_contract. | MOD-3 Phase 1 (trivial) |
| A.2 | 7-day quiescence incomplete | n/a | Time-gated | Wait until 2026-04-30T00:35:57Z; verify no arena restart + no feat commits. | **2026-04-30** |
| A.3 | None — already CLEARED | n/a | n/a | n/a | — |
| Operational | 0-1 infra blockers | — | — | All 10 RESOLVED or DEFERRED per `infra_blocker_report.md` + MOD-2 Phase 1/2/4 | COMPLETE |

## 2. Summary counts

| Category | Count |
|---|---|
| CRITICAL blockers | **2** (both A.1 amendments) |
| HIGH blockers | **4** (all A.1 amendments) |
| MEDIUM blockers | **6** (5 A.1 soft amendments + 1 A.2 time-gated) |
| LOW blockers | 1 (A.1 trivial) |
| Total actionable blockers | **13** |
| Time-gated only | 1 (A.2) |

## 3. Shortest path to CLEARED

1. **MOD-3 Phase 1 — CRITICAL + HIGH amendments** (6 changes, estimated 1 working session)
   - All text pre-authored in `mod1_delta_after_gemini.md` §1
   - Commit pattern: `docs(zangetsu/mod-1-amendments): apply gemini round-2 findings`
2. **Gemini round-3 review** of amended MOD-1 corpus
   - Target: ACCEPT (no amendments required)
3. **Wait for quiescence expiry** — 2026-04-30T00:35:57Z
4. **Gate-A transition**: PARTIALLY_BLOCKED → CLEARED_PENDING_QUIESCENCE → CLEARED (instantly at T=quiescence marker)

## 4. Worst-case path

If Gemini round-3 rejects again:
- Iterate amendments
- Quiescence clock does NOT restart (spec says `feat(` commits reset; `docs(` do not)
- Amendments are `docs(` commits → quiescence clock preserved

## 5. Governance note

This matrix does NOT close Gate-A. It enumerates what must close Gate-A. Any future team member claiming "Gate-A cleared" must cite specific evidence that each CRITICAL + HIGH row has been resolved, via commit SHA + Gemini round-3 verdict.

## 6. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 10. Labels applied | CRITICAL / HIGH / MEDIUM / LOW per row; severity column explicit |

## 7. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 14 actionable blockers enumerated covering all 3 Gate-A sub-conditions |
| Silent failure | PASS — every CRITICAL has explicit remediation; no "deferred indefinitely" entries |
| External dep | PASS — amendments depend only on documentation + GitHub Actions workflow (both available) |
| Concurrency | PASS — amendments are sequential, not concurrent with other MOD work |
| Scope creep | PASS — matrix lists blockers only; does not apply them |
