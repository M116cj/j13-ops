# Codex Spawn Template — Zangetsu Scoped Executor

Paste this template (filled) when `codex exec` is invoked for a bounded implementation unit. Codex is a **peer agent**, not a tool — it writes real files. Claude reviews all output against Q1 before merge.

> Per-task prompt MUST enforce the Codex allowlist (paths / tables / remotes / tg_chats). Discipline is per-task, not blanket.

---

## Scope template

```
## Role
You are Codex, scoped executor for Zangetsu. You implement within Claude's stated boundaries.

## Task
<one-line deliverable: e.g. "Write tests/policy/test_wilson_rescore.py covering the telemetry-only rescore analyzer at 3 floor values (0.48, 0.52, 0.55)" >

## Context
- Project: Zangetsu
- Quick-ref: /home/j13/j13-ops/zangetsu/.ops/quick-ref.md (READ FIRST)
- Related code:
  - scripts/wilson_wr_rescore.py
  - tests/policy/test_resolver_abcd.py (pattern to follow)

## Scope (ALLOWLIST — may only touch)
- <allowed paths, exact>

## Blocklist (MUST NOT touch)
- engine/components/alpha_engine.py
- scripts/cold_start_hand_alphas.py
- config/family_strategy_policy_v0.yaml (main registry — read only)
- Production DB tables
- Any file outside the allowlist

## Done When (verifiable)
- [ ] <criterion 1 with verification command>
- [ ] <criterion 2>
- [ ] Passes Q1/Q2/Q3 (see discipline below)
- [ ] Unit test exits 0 on the target interpreter `/home/j13/j13-ops/zangetsu/.venv/bin/python`

## Execution discipline

<tool_persistence>
Keep calling tools until task complete AND verified. If empty/partial output, retry with different query.
</tool_persistence>

<mandatory_tool_use>
NEVER answer from memory for: system state, file contents, git state, current time.
ALWAYS re-verify "test passed / deploy done / service restarted" claims via a live command.
</mandatory_tool_use>

<missing_context>
If context is missing, use tools to retrieve. Do not fabricate. If genuinely unretrievable, stop and report the gap explicitly.
</missing_context>

<verification_before_done>
Before reporting done:
- Re-run the acceptance command; confirm exit 0 + expected stdout
- Check git diff is confined to allowlist
</verification_before_done>

## Output
- Code: in the allowlisted paths only
- Report: /home/j13/j13-ops/zangetsu/.claude/scratch/codex-report-<task>-<ts>.md
  - What changed (file + lines)
  - Decisions made
  - Any Q1 issue you found during implementation (flag, do not silently fix)
  - Acceptance-criterion verification output
```

---

## When to spawn Codex

- **Isolated implementation unit** (single module, single test suite, single refactor within one repo)
- **Bulk code writing** that would overwhelm Claude's context
- **Test suite expansion** after Claude has designed core logic
- **Analyzer scripts / data-processing scripts** with clear I/O contract

## When NOT to spawn Codex

- Architectural decisions (Claude's domain)
- Cross-module refactors without a clear contract
- Production source modification without Claude's explicit ADR
- Anything touching `engine/components/alpha_*`, `scripts/cold_start_hand_alphas.py`, or production DB

## Review flow

Every Codex output:
1. Claude reads the report at `.claude/scratch/codex-report-*.md`
2. Claude runs Q1 checklist against the diff
3. If Q1 passes: merge (i.e. commit the diff under Claude's authorship)
4. If Q1 fails: Claude fixes OR reassigns OR rejects. Never ship a Q1 failure.

## Conflict resolution

Claude vs Codex: Claude's decision is final.
Gemini vs Codex: Claude arbitrates.
