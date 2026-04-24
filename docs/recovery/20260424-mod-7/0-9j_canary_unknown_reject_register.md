# 0-9J CANARY — UNKNOWN_REJECT Register

Per TEAM ORDER 0-9J §12.

## 1. Top-line

| Metric | 0-9G SHADOW | 0-9H re-SHADOW | 0-9J CANARY |
|---|---:|---:|---:|
| Total rejection events | 3,651 | 3,651 | 3,651 |
| UNKNOWN_REJECT events | 813 | 0 | **0** |
| UNKNOWN_REJECT ratio | 22.27 % | 0.00 % | **0.00 %** |
| Unique unmapped raw-string patterns | 5 | 0 | **0** |
| A2 UNKNOWN_REJECT ratio | 23.9 % | 0.00 % | **0.00 %** |

## 2. Residual unmapped patterns

**None.**

```python
# Post-0-9H RAW_TO_REASON coverage confirmed on 0-9J CANARY:
unmapped_raw_top20 = {}   # empty
```

All 3,651 rejection events in the observation window were classified to a canonical reason. The 0-9H V10 prefix aliases (`"[V10]: pos_count"` and `"[V10]: trades"`) remain effective on the current main-branch state (`665298fb`).

## 3. Stability vs SHADOW

- Classification is **deterministic** — same log stream, same output between 0-9H re-SHADOW and 0-9J CANARY (both produce 3,651 mapped, 0 unknown).
- No new raw-string patterns surfaced in 0-9J relative to 0-9G/0-9H. Expected behaviour: Arena is frozen since MOD-3; no Arena process has produced fresh log lines since 2026-04-23T00:35Z (the engine.jsonl mtime). Any new raw-string variants would only appear after Arena is unfrozen AND a new V10 / A2 code path is added — neither has occurred.

## 4. Future watch list

When Arena is eventually unfrozen (requires a separate j13-authorized order that is NOT 0-9J), future canaries should watch for:

- New `A2 REJECTED ... [V11]:` or similar suffix variants if `arena23_orchestrator.py` is updated.
- A0 / A4 / A5 rejection patterns (zero observations in current window since Arena is frozen and no A0→A4→A5 pipeline runs have happened in the observation period).
- New governance-level rejections emitted by `calcifer/zangetsu_outcome.py` if §17.3 outcome watch is ever wired to trigger on specific rejection patterns.

## 5. No mapping patch needed under 0-9J

The existing taxonomy (as merged in PR #9, commit `0b41550c`) remains sufficient for the current production-adjacent state. No 0-9J-scope patch to `RAW_TO_REASON` is required.

Should future observation uncover new unmapped strings, the established pattern (add prefix alias to `RAW_TO_REASON` + test case) is the minimal-scope fix template and can be applied by a future order.

## 6. Register state

- Register status: **CLEAN** (0 entries).
- Last update: 0-9H (2026-04-24, PR #9) resolved the previous 5-pattern register.
- Next required action: none from 0-9J. Future orders may revisit if observation window changes or Arena state changes.
