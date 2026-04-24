# P7-PR1 SHADOW — Go / No-Go Verdict

Per TEAM ORDER 0-9G §10 + §16.

## 1. Verdict

```
VERDICT = RED
```

Rationale: UNKNOWN_REJECT ratio **22.27 %** exceeds the 0-9G §5 threshold (> 15 % = RED).

## 2. Decision matrix

| Next action | Recommended? | Reason |
|---|---|---|
| **Proceed to CANARY** | **NO** | UNKNOWN_REJECT ratio must fall < 10 % before CANARY is safe. |
| **Apply P7-PR1 taxonomy mapping patch** | **YES (primary recommendation)** | 5 V10 A2 patterns identified; surgical 3-line addition to `RAW_TO_REASON` projected to drop UNKNOWN_REJECT to ~0 %. |
| **Extended SHADOW (no patch)** | NO | The unmapped patterns are enumerated; no additional observation is needed before patching. |
| **Proceed to P7-PR2** | **NO** | Taxonomy coverage must be green before the next module migration is attempted. |
| **Abandon Phase 7** | — | Not indicated by observation; SHADOW produced clean evidence chain. |

## 3. Positive signals

- Telemetry classifier operated correctly on 322,792 log lines without raising.
- Classification is deterministic: same raw string always yields same canonical reason.
- 76.9 % of all rejections map cleanly to SIGNAL_TOO_SPARSE; 0.8 % to OOS_FAIL; A1/A3 100 % mapped.
- Arena 2 identified as the 93 %-dominant rejection stage — this is the diagnostic signal Phase 7 was supposed to surface.
- Zero forbidden controlled-diff fields.
- Zero runtime mutation (Arena + config + systemd + branch protection SHAs all unchanged pre → post).
- Behaviour-invariance tests (46/46) pass before and after SHADOW.

## 4. Negative signals

- 22.27 % UNKNOWN_REJECT ratio (RED threshold).
- 5 A2 V10 raw-string patterns not covered by `RAW_TO_REASON`.
- deployable_count provenance is partial — SHADOW focused on rejection classification, not on full candidate lifecycle join. Full provenance requires a richer parser (A1 promoted events joined with A2/A3/A4 outcomes).

## 5. Mitigation path to GREEN

1. **Separate authorized order** to apply the P7-PR1 taxonomy mapping patch (3-line addition to `RAW_TO_REASON` + 1 new test asserting V10 patterns map to SIGNAL_TOO_SPARSE).
2. Merge via signed PR with Gate-A + Gate-B (both now trigger post-0-9F).
3. Re-run SHADOW against the same log set. Expected UNKNOWN_REJECT ratio: < 1 %.
4. If confirmed GREEN, evaluate CANARY readiness.

Estimated scope of the patch: ~10 insertions, 0 deletions, 1 test file touched.
No alpha / Arena / threshold / runtime change. Controlled-diff expected EXPLAINED.

## 6. Summary wording

```
P7-PR1 SHADOW verdict: RED
UNKNOWN_REJECT ratio: 22.27 %
Dominant rejection stage: A2 (93 %)
Dominant reason: SIGNAL_TOO_SPARSE (76.9 % mapped; +22.3 % unknown → ~100 % post-patch)
Gap: 5 A2 V10 raw-string patterns unmapped
Recommendation: P7-PR1 taxonomy mapping patch (SEPARATE order required)
```

## 7. STOP

No further Phase 7 action is authorized under 0-9G. Awaiting j13 decision on the next order:
- `TEAM ORDER 0-9H` (or similar) for the taxonomy mapping patch, OR
- alternative Phase 7 direction.

STOP.
