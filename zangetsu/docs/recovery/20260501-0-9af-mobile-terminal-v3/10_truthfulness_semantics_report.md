# 10 — Truthfulness Semantics Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 6

## Rules Enforced

| Rule | Where enforced | Verified by |
|---|---|---|
| No fake zero | view-models return None (not 0); templates render 'NO DATA' / 'NO MATCH' / 'NOT_REACHED' / 'no survivors' for empty states | test_no_fake_zero_in_overview_when_data_exists |
| NOT_EVALUATED ≠ REJECTED | topbar has separate `UNK` / `NEV` / `ERR` pills + arena VM tracks counts in distinct fields | test_not_evaluated_pill_distinct_from_rejected_in_topbar |
| Survivor ≠ Near-survivor | /survivors page renders TWO distinct `<table>` blocks from TWO separate artifacts | test_survivors_strictly_separated |
| Survivor ≠ Deployable | No template claims a survivor is deployable; deployable_count VIEW remains 0 | live VIEW query post-merge |
| A3+ ≠ 0 | /funnel template hard-codes A3/A4/A5 rows to display 'NOT_REACHED' string with .na class | template inspection + screenshot |
| MISSING freshness | runtime_health.freshness_for() returns 'MISSING' for non-existent files; topbar pill shows gray | V1 freshness test (still passing) |
| ERROR freshness | parse / stat exceptions surface as 'ERROR' state with red pill | V1 + V3 health endpoint tests |
| feedback weights honest | rejection_feedback returns 'EMPTY_WITH_REASON' when no rejections; /feedback template renders 'EMPTY_WITH_REASON' string | template + view-model |
| Read-only HTTP enforcement | FastAPI route enumeration test forbids POST/PUT/PATCH/DELETE | test_app_is_read_only_no_write_paths |
| No write call patterns in source | grep for to_sql / .execute / subprocess / os.system / shutil.rmtree | test_no_write_call_patterns |
| No arena_pipeline / shadow_batch_runner imports | grep across dashboard_mobile/ | test_no_arena_pipeline_or_runner_imports |

## Per-Page Empty-State Rendering

| Page | When data missing | Rendered as |
|---|---|---|
| / | run_summary missing | 'NO BATCH FOUND' empty card |
| / | reject_reason_summary empty | 'NO DATA' inside depth panel |
| /funnel | shadow_batch_results missing | A3/A4/A5 always shows 'NOT_REACHED'; side split → 'NO DATA' |
| /candidates | results missing or filter returns 0 rows | 'NO MATCH' single-row table |
| /candidate/{cid} | unknown cid | HTTP 404 (test enforced) |
| /rejects | no REJECTED rows | empty arrays render no rows; KPI 0 OK because real |
| /survivors | survivor file missing | per-table 'no survivors' / 'no near-survivors' |
| /feedback | no feedback artifacts | 'EMPTY_WITH_REASON' info |
| /health | always renders per-source state table | each source's MISSING/ERROR shows as red tag |

## A3 Treatment

A3 funnel row is hard-coded to display `'NOT_REACHED'` (gray, .na class) because shadow orders never invoke `services.arena_gates.arena3_pass`. This is product-correctness: distinguishes "data layer not yet exercised" from "data is zero".

## Read-Only Enforcement (defense in depth)

1. **HTTP layer**: `test_app_is_read_only_no_write_paths` enumerates routes and asserts no POST/PUT/PATCH/DELETE.
2. **Template layer**: `<form method="get">` only — no POST forms anywhere.
3. **Code layer**: `test_no_write_call_patterns` greps for forbidden patterns.
4. **OS layer**: systemd `ProtectHome=read-only` + `ProtectSystem=strict` + `PrivateTmp=yes`.
5. **Network layer**: bind `100.123.49.102` (Tailscale) only; no public reachability.

## Gemini V3 UX Review

**`PASS`** (gemini-2.5-flash, env-loaded key, never echoed/committed).

(First attempt's literal misinterpretation of "OKX-style" as "is this OKX product" returned a meta FAIL. Retry with explicit "NOT OKX — borrow patterns" framing returned PASS.)
