# 01 — j13 Checkpoint Decision

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Sub-order:** TEAM ORDER 0-9Y-CHECKPOINT-HORIZON-VS-FEATURE-EXPANSION
**Phase:** 8
**Decision date (UTC):** 2026-04-28
**Decided by:** j13

## Decision

```
OPTION A: OP1 → TF2 → HE1 → HE2 → HE3 → HE4 → HE5
```

### Yes-vote summary

| Question | j13 answer |
|---|---|
| Add `TEAM ORDER 0-9Y-OP1-PRIMITIVE-REGISTRATION` to master plan? | **YES** |
| Add `TEAM ORDER 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE` to master plan? | **YES** |
| Three options A / B / C — which? | **A** |
| Phase 3-5 (now extended to OP1+TF2+HE1+HE2+HE3) timing | **Next session** |

## j13's stated rationale (verbatim)

> horizon-only 不夠。
>
> 目前 grammar 本身缺 9 個已實作但未註冊 primitives，再加上 trade-frequency 已明確顯示低頻/強信號更有利。
>
> 所以最佳路徑是：
> 1. 先補 grammar 搜索能力
> 2. 再加 signal aggregation prototype
> 3. 最後才跑 horizon ensemble

## j13's one-line summary

> 先讓 A1 搜得更好，再讓它交易得更少更強，最後才測 180/240/360 horizon。

## Decision logic check

| Decision driver | TF1/FS1 evidence | Decision matches evidence? |
|---|---|---|
| FS1 says grammar lacks 9 primitives → horizon-only test would be contaminated | OP1 chosen as Step 1 | ✓ |
| TF1 says sparse beats dense by +1.04 bps net delta with strong corroboration | TF2 chosen as Step 2 (after OP1, before horizon) | ✓ |
| HE0 design spec assumes horizon plumbing on top of existing grammar | HE1-HE3 placed AFTER OP1+TF2, so they leverage the expanded grammar | ✓ |

## Constraints reinforced by j13

> 限制：不改 validation/不改 cost/不改 A2_MIN_TRADES/不開 alpha_zoo/不開 CANARY/不開 production

These are the hard rules carried forward into every Step 1-9 sub-order.

## Status

Decision RECORDED. Master plan SUPERSEDED by Option A revised sequence (see `02_revised_master_sequence.md`). HE0 design spec from Phase 2 (`a5f7cabd`) remains valid; HE1 will reference it as input.

This Phase 8 checkpoint completes the original master order's PRE-checkpoint sequence and authorizes the POST-checkpoint sequence to begin in a fresh execution session.
