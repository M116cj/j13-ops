# 02 — Patch Report (Subprogram B3)

## Files changed

```
 calcifer/calcifer_v071_watch.sh                |  66 +++++  (additive, +66 lines)
 calcifer/calcifer_outcome_predicate.py         |  61 +++++  (new file, pure-Python predicate helper)
 zangetsu/tests/test_b3_calcifer_outcome_predicate.py  | 130 +++++  (new file, 9 tests)
 3 files changed, ~257 insertions(+), 0 deletions(-)
```

## Hunk summary

### `calcifer/calcifer_v071_watch.sh` (+66 lines after the existing process-color file write)

New tail block:

```bash
DEPLOY_BLOCK_FILE=/tmp/calcifer_deploy_block.json

if [ "$WORKER_UP" -eq -1 ]; then
    :  # workers not running; do not judge
else
    status_row=$(PSQL "SELECT COALESCE(deployable_count,0), last_live_at_age_h FROM zangetsu_status")
    IFS="|" read -r DEPLOYABLE_COUNT LAST_LIVE_AGE <<< "${status_row:-0|}"

    if [ "${DEPLOYABLE_COUNT:-0}" -gt 0 ]; then
        rm -f "$DEPLOY_BLOCK_FILE" 2>/dev/null
    elif [ -z "${LAST_LIVE_AGE:-}" ]; then
        # NULL: cold-start
        cat > "$DEPLOY_BLOCK_FILE" <<JSON
{
  "status": "UNKNOWN_BLOCKED",
  "iso": "$TS",
  ...
  "predicate": "0-9Y-B3-NULL-SAFE",
  "writer": "calcifer_v071_watch.sh"
}
JSON
    else
        # Numeric comparison via awk (bash cannot compare floats portably)
        age_gt_6=$(awk -v a="${LAST_LIVE_AGE:-0}" 'BEGIN { print (a > 6.0) ? 1 : 0 }')
        if [ "$age_gt_6" = "1" ]; then
            # RED: regression
            cat > "$DEPLOY_BLOCK_FILE" <<JSON ...
        else
            rm -f "$DEPLOY_BLOCK_FILE" 2>/dev/null
        fi
    fi
fi
```

### `calcifer/calcifer_outcome_predicate.py` (new, 61 lines)

Pure-Python mirror of the bash predicate with two functions:

```python
def evaluate_deploy_block_state(deployable_count, last_live_at_age_h):
    if deployable_count > 0: return None
    if last_live_at_age_h is None: return "UNKNOWN_BLOCKED"
    if last_live_at_age_h > 6.0: return "RED"
    return None

def block_file_should_exist(deployable_count, last_live_at_age_h):
    return evaluate_deploy_block_state(...) is not None
```

This module is **not imported by the bash script** — the bash script is the canonical writer. The Python helper is the **single-source-of-truth for the predicate semantics** so the test suite can verify the logic without parsing bash.

### `zangetsu/tests/test_b3_calcifer_outcome_predicate.py` (new, 9 tests)

Exhaustive coverage of the 4 logical states + boundaries + bypass-impossibility property + false-green prevention:

1. healthy state (dc > 0): no block regardless of age (5 ages × 3 dc = 15 sub-cases)
2. cold-start (dc=0, age=None): UNKNOWN_BLOCKED
3. regression (dc=0, age > 6): RED (5 ages)
4. recovery window (dc=0, 0 ≤ age ≤ 6): no block (5 ages)
5. boundary at exactly 6.0: no block (strict >, not >=)
6. boundary at 6.000001: RED
7. false-green prevention: explicit assertion against the pre-fix behavior
8. no-bypass property: any (dc=0, age != [0..6]) MUST produce a block
9. type tolerance: 0.0 age handled correctly

## Invariant preservation

| Invariant | Preserved? |
|---|---|
| process-side color file (`/tmp/calcifer_process_<color>.json`) semantics | YES — unchanged |
| Worker-uptime grace handling | YES — unchanged |
| Process exception thresholds (RED at >1000, YELLOW at >100) | YES — unchanged |
| Cron cadence (15 min) | YES — unchanged |
| Cost model | NOT TOUCHED |
| Validation gates (A2_MIN_TRADES, A3_*, A4_*) | NOT TOUCHED |
| BacktestResult schema | NOT TOUCHED |
| Champion promotion semantics | NOT TOUCHED |
| Conservation invariant (PR #50) | NOT TOUCHED |

## Risk assessment

- **R-4 (Calcifer NULL-safety patch creates false RED on cold-start)**: PARTIALLY ACCEPTED. Cold-start IS the intended new state to flag — that is the bug being fixed. The verdict separates `UNKNOWN_BLOCKED` (cold-start) from `RED` (regression) so the §17.3 deploy-block enforcement can distinguish the two if a future order needs differentiated policy.
- **R-9 (existing test failure)**: verified PASS — 121/121 tests including 9 new B3 + 10 B1 + 102 pre-existing.
- **No risk to runtime behavior of A1/A23/A45 workers**: B3 only modifies a Calcifer cron script + adds a Python helper; no zangetsu source code changes.

## Why no `zangetsu/services/...` change

The original §17.3 spec mentions Calcifer polls. The implementation is on the Calcifer side, not the zangetsu pipeline side. Therefore B3 is correctly scoped to `calcifer/` directory.

The only zangetsu-side touch is the test file under `zangetsu/tests/` because that's where the project's pytest runner is configured (`zangetsu/pytest.ini`).
