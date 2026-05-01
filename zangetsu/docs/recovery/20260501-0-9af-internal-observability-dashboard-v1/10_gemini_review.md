# 10 — Gemini Adversarial Review

**ORDER**: 0-9AF — Phase 6

## Status

`PASS_WITH_NOTES`

## Retry Configuration

```
Auth:        env GEMINI_API_KEY (env-loaded from /home/j13/.gemini/settings.json,
             never echoed, never committed)
CLI version: gemini 0.35.3
Model:       gemini-2.5-flash (after gemini-3.1-pro free-tier quota exceeded)
Timeout:     90 s
Prompt:      compact dashboard summary + binary question
```

## Gemini Response (verbatim, sanitized)

> "PASS_WITH_NOTES. While tests pass and no DB writes occur, consider if 'A3 shows NOT_AVAILABLE' indicates a critical data issue needing resolution."

## Note Adjudication

Gemini's note suggests `A3 shows NOT_AVAILABLE` may indicate a critical data issue. Adjudicated by Claude (lead, per CLAUDE.md §5):

- A3 = NOT_AVAILABLE is **expected and intended** for current SHADOW orders (0-9AB / 0-9AC / 0-9AD never invoke `services.arena_gates.arena3_pass`, which requires segmented holdout).
- A3 represents a future Arena gate that scale-up orders (0-9AE+) will exercise. Showing `NOT_AVAILABLE` is the truthful representation per the order's no-fake-zero rule.
- This is a **product correctness** signal, not a data issue: the dashboard correctly distinguishes "data layer not yet exercised" from "data is zero".

The note is acknowledged as a UX consideration: a future enhancement could add a one-line subtext on the A3 page explicitly saying "Will populate when scale-up orders exercise A3." This is added to the optional-improvements list rather than treated as a blocker.

## Self-Review Cross-Check (10 review questions per order §11)

| # | Question | Answer |
|---|---|---|
| 1 | Does the dashboard clearly show real state? | YES — every page surfaces source path + freshness badge |
| 2 | Distinguish no data from zero? | YES — explicit `'NO DATA'` / `MISSING` / `NOT_AVAILABLE` strings; tested |
| 3 | Distinguish NOT_EVALUATED from REJECTED? | YES — separate fields in ArenaSummary; tested |
| 4 | Distinguish near-survivor from survivor? | YES — two separate artifacts + two separate tables; tested |
| 5 | Overview helpful for fast operator understanding? | YES — 8 KPI cards + funnel + reject reasons + status donut + top symbols |
| 6 | Arena pages useful and understandable? | YES — KPI band + side split + per-symbol table |
| 7 | Charts not misleading? | YES — bar charts ordered by value; donut shows actual counts; A3 shows banner not 0 chart |
| 8 | Freshness clearly shown? | YES — per-source state in System Health + per-page badges |
| 9 | Read-only and safe? | YES — no write actions in any page; ProtectHome=read-only at systemd layer |
| 10 | Avoids control-plane creep? | YES — no buttons trigger mining / execution / writes |

## Critical Findings

None.

## High Findings

None.

## Medium Findings

- Gemini's A3 note is a UX clarification opportunity (not a defect). Address in V2 by adding inline explanation on A3 page.

## Required Fixes Before Merge

None.

## Optional Improvements After Merge

- Add "will populate when 0-9AE/AF/AG scale-up orders run A3" subtitle on the A3 page.
- Add a multi-batch trend page (compare last N batches' reject distributions).
- Add Calcifer-side uptime probe consuming `/_stcore/health`.
- Add screenshot generator to systemd timer for periodic capture.

## Final Recommendation

`PASS_WITH_NOTES` — proceed to merge. The note is informational (no fix required).
