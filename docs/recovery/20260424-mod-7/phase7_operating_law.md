# Phase 7 Operating Law

- **Scope**: Codifies the Phase 7 operating rules from 0-9 §1. Authoritative reference for any agent or human executing under Phase 7.
- **Actions performed**: Transcribed + annotated rules; cross-referenced with Controlled-Diff + Gate-B enforcement points.
- **Evidence path**: 0-9 §1 Hard rules 1-10.
- **Observed result — the law (verbatim preservation)**:

### 1.1 Flow (every Phase 7 change must follow)
```
local branch
 → signed commit
 → PR
 → Gate-A workflow
 → Gate-B module migration workflow
 → review evidence
 → merge only if allowed
 → SHADOW rehearsal
 → CANARY rehearsal
 → promotion decision
```

### 1.2 Hard rules (UNIVERSAL — apply everywhere, all branches)
1. No direct push to main.
2. No unsigned commit.
3. No admin-bypass.
4. No force push.
5. No production rollout without SHADOW + CANARY evidence.
6. No threshold tuning disguised as migration.
7. No alpha logic change without explicit module-scoped PR.
8. No Arena promotion without rejection taxonomy and rollback path.
9. No multi-module migration in one PR unless explicitly justified.
10. Every PR must include evidence artifacts.

- **Forbidden changes check**: This doc does not change anything; it records the law. Any future agent or commit that violates rules 1-10 is automatically a STOP trigger.
- **Residual risk**:
  - Rule 2 ("No unsigned commit") is universal — it applies to feature branches too, not only main. This means from Alaya, no push is currently permissible (see `mod7_stop_report.md`).
  - Rule 9 is the main vector for scope creep; enforced by Gate-B module-scoping + Controlled-Diff surface.
- **Verdict**: Law is in force. Current MOD-7 halt is a correct application of the law (rule 2 + STOP #1 + STOP #6).
