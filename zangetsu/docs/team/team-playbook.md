# Zangetsu Team Playbook — High-Intensity Phase

Authored 2026-04-22 by Claude (Lead). Companion to `spawn-gemini.md`, `spawn-codex.md`.

---

## Five-agent team

| Agent | Role | Model | When auto-invoke |
|---|---|---|---|
| **Claude (Lead)** | Architecture, core impl, Q1/Q2/Q3, j13 interface | Opus 4.7 1M | Always primary |
| **Gemini** | Adversary + infra config + million-token analysis | Gemini Pro | Major arch / pre-deploy / 對抗 review / infra config |
| **Codex** | Scoped executor for bounded implementation units | gpt-5.1-codex-max | Bulk code / test suites / analyzers |
| **Calcifer** | Alaya infra guardian | Gemma4 E4B (Ollama 11434) | Pre/post-deploy / DB health / container issues / GPU diagnostics |
| **Markl** | Research analyst + second-opinion | Gemma3 12B (Ollama Mac 11434) | Backtest result analysis / strategy fitness interpretation / hypothesis generation / report drafting |

Only Claude interfaces with j13 directly. Others produce inputs; Claude judges.

---

## Standard workflow by complexity

### Solo (≤ 45 min, linear deps, Simple)
Claude only. Quick-ref first. Execute. Q1/Q2/Q3 before done.

### /build (45 min – 2 hr, Medium)
- Claude: core logic + integration (parallel)
- Codex: test suite (blocked by core logic complete)
- Gemini: adversarial review (parallel)
- Merge → full test → Q1/Q2/Q3 → commit

### /team (> 2 hr, Complex, cross-module)
Four phases, **no skipping**:

**Phase 1 — Recon (Claude + Gemini, ≤ 2 min)**
- Read quick-ref.md
- Read project CLAUDE.md
- Gemini does `gemini -p "..." --all-files` full-codebase scan
- Define minimum deliverable
- **Gate**: if deliverable unclear → ask j13, do not guess

**Phase 2 — Task Design (Claude only)**
For each sub-task:
- Verifiable deliverable
- Acceptance criteria + verification command
- File scope (allowlist + blocklist)
- Dependencies
Zero overlap between agents.

**Phase 3 — Spawn**
Use `spawn-gemini.md` / `spawn-codex.md` templates. Include:
- Quick-ref read requirement
- Execution discipline block (`<tool_persistence>` etc.)
- Allowlist + blocklist
- Done-when criteria
- Output path + ≤200 line cap

Claude may write integration glue; Claude MUST NOT write feature logic assigned to others. If a teammate is blocked > 5 min, Claude intervenes.

**Phase 4 — Integration (Claude only)**
- Merge → full test → fix → commit → Q1/Q2/Q3 pass
- Report to j13
- Retrospective → `docs/retros/YYYYMMDD.md`

---

## Pre-task ritual (every task, no exceptions)

1. **status VIEW check**: `docker exec -e PGPASSWORD=... deploy-postgres-1 psql ... -c 'SELECT * FROM zangetsu_engine_status;'`
2. **Calcifer block check**: `cat /tmp/calcifer_deploy_block.json`
3. **commit pin**: `git -C /home/j13/j13-ops/zangetsu rev-parse HEAD`
4. **Read** `.ops/quick-ref.md` (don't re-grep same things)
5. **Classify** complexity + risk (§9 intake)
6. **Decide** Solo / /build / /team

If pipeline dead (deployable_count=0 + age>6h) AND task is alpha-facing:
- Escalate to j13 before running decoration experiments
- P0 (root cause) takes precedence over any decoration

---

## Conflict resolution matrix

| Disagreement | Resolution |
|---|---|
| Claude vs Gemini | Document both, escalate j13. No proceed until arbitrated |
| Claude vs Codex | Claude final |
| Gemini vs Codex | Claude arbitrates |
| Q1 reviewer (Gemini) vs Q2/Q3 | Q1 has veto |
| Q2 vs Q3 | Q2 wins |

---

## Context management for high-intensity phase

- **Output > 200 lines** → write to `.claude/scratch/{task}-output.txt`, grep from file
- **Context at 70%** → write `session-state.md` first, then `/compact`
- **Full-codebase analysis needed** → `gemini -p --all-files` → scratch
- **Teammate finding** → `.claude/scratch/team/{role}-findings.md` + brief status
- **Task switch** → `/clear`
- **Same-JSONL reuse pattern**: if multiple tasks post-process same source data (e.g. all based on one 140-cell run), do NOT rerun — use counterfactual / rescore analyzers against the stored JSONL

---

## End-of-session checklist (Claude MUST run)

- [ ] All final_report.md artifacts under `results/` — snapshot to run dirs ✓
- [ ] Session's code changes → commit with clear scope (feat/fix/refactor)
- [ ] ADRs under `docs/decisions/YYYYMMDD-*.md` for every decision-grade output
- [ ] Retrospective `docs/retros/YYYYMMDD.md` if /team was used
- [ ] AKASHA 9-segment JSON post (if `AKASHA_PROJECT` env set)
- [ ] `git status` clean (or blockers documented)
- [ ] Session-local scratch (`/tmp/*_wrapper.py`) archived or deleted if superseded
- [ ] quick-ref.md updated if any new shared convention emerged

---

## Verdict writing protocol (3-choice, mechanical)

When writing `YES / MIXED / NO` verdicts:

1. **Analyzer** (not human) computes pass/fail on each rule bullet
2. Claude's report cites the analyzer output, does NOT re-reason the bullets from memory
3. If analyzer says NO/MIXED but Claude's narrative suggests YES, trust the analyzer and investigate the narrative bias
4. **Calibration watchlist**: "train widens, val absorbs death" → this is NOT MIXED. It is NO. The MR-generalization case on 2026-04-22 proved this — j13 corrected Claude's initial MIXED to NO.

---

## Mechanical rules Claude must assert (not recall)

- `deterministic critical path` ⇒ same commit + same inputs ⇒ **bit-exact** outputs (no rerun needed for post-processing)
- `generate_alpha_signals` namespace capture ⇒ patch `cold_start_hand_alphas.generate_alpha_signals`, not only `engine.components.alpha_signal.generate_alpha_signals`
- `exit_atr=0 across > 10,000 trades` ⇒ A1 ATR stop is dead; all observed differences come from signal-gen / entry-filter, not exit mechanics
- `exception_allow_list_hit=True` ⇒ override is applied only if `first_gate_reached == a1_val_low_wr`; other gates do not trigger override
- `fallthrough_to_main=True` on non-allow-list cells ⇒ no exception effect; row must look identical to a no-overlay run

---

## Known traps (earned through experience)

- **Pre-bash hook** blocks `curl ... || head` and `grep -E 'a|b|c'` — budget extra retries or use `grep -e PATTERN` alternatives
- **psql not on host**; use `docker exec -e PGPASSWORD=... deploy-postgres-1 psql -U $ZV5_DB_USER -d $ZV5_DB_NAME -c '...'`
- **env vars**: always `set -a; . /home/j13/j13-ops/zangetsu/secret/.env; set +a` before any shadow / prod command
- **.bak_pre_*** backups litter the repo; git has history, safe to delete post-session
- **Counterfactual predictions vs reality**: predicted 17-cell unlock, actual 2-cell. Always compute the distribution of the key variable before claiming unlock count.
