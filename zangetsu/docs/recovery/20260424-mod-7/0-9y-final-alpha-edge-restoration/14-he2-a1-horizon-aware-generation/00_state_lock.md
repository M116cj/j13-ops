# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-HE2-A1-HORIZON-AWARE-GENERATION
**Date**: 2026-04-29
**Phase**: 0 / 8

## Git
- Branch: `main`
- HEAD: `bbd6fb427548bf3ca8dc123c2db1cb2754258b86` (post-HE1, signed ED25519)
- origin/main: `bbd6fb427548bf3ca8dc123c2db1cb2754258b86` ✅ in-sync
- Working tree (zangetsu): only `zangetsu/logs/engine.jsonl.1` (runtime log) — no source dirty.

## HE1 import sanity
```
$ python3 -c "from zangetsu.services.horizon_config import get_horizon_config, select_horizon; ..."
active_horizons=(60,) mode=FIXED fixed=60
selected=[60, 60, 60, 60, 60, 60, 60, 60]
```
HE1 import path: `zangetsu.services.horizon_config` (note: master order spec sample uses `zangetsu.engine.components.horizon_config` which is a **spec typo** — actual location per HE1 PR #69 is `zangetsu/services/`. HE2 will preserve this canonical path).

Default config (env unset):
- `active_horizons = (60,)`
- `mode = FIXED`
- `fixed_horizon = 60`
- All 8 sampled rounds select horizon = 60 ✅ baseline preserved

## TF stack present
| Module | Path | Status |
|---|---|---|
| TF2 helper | `zangetsu/services/signal_aggregation.py` | ✓ |
| TF3 shadow | `zangetsu/services/tf3_shadow.py` | ✓ |
| TF4 production config | `zangetsu/services/aggregation_config.py` | ✓ |
| HE1 horizon config | `zangetsu/services/horizon_config.py` | ✓ |

## TF + HE1 stack tests (regression)
```
pytest -q test_signal_aggregation.py test_tf3_shadow.py test_tf4_aggregation_config.py test_he1_horizon_config.py
→ 37 passed in 0.39s ✅
```

## TF / HE1 OFF default verification
- Live worker env (sample PID 2963114): no `ARENA_HORIZON_*` / `ACTIVE_A1_HORIZONS` / `ALPHA_FORWARD_HORIZON` / `ARENA_AGGREGATION_*` / `ARENA_TF3_SHADOW` set → confirmed baseline mode

## Order status
| Order | Status |
|---|---|
| OP1 | COMPLETE (`82056123`) |
| TF2 | COMPLETE (`3decabd4`) |
| TF3 | COMPLETE (`0cef908d`) |
| TF4 | COMPLETE (`986932df`) |
| HE1 | COMPLETE (`bbd6fb42`) |

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Repo dirty with unexplained source changes | ❌ no — only runtime log |
| HEAD != origin/main | ❌ no |
| HE1 horizon_config import fails | ❌ no — verified |
| A1 runtime dead | ❌ no (workers running, last batch verified live) |
| DB unavailable | ❌ no (Phase 0 ran end-to-end with no infra failure) |
| Telemetry regression | ❌ no — 37 tests PASS, baseline batches showing horizon/aggregation off |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.

## Spec-actual import discrepancy note
The TF order 5-6 spec includes a sample import:
```python
from zangetsu.engine.components.horizon_config import get_active_a1_horizons, select_horizon
```
HE1 placed the module at `zangetsu/services/horizon_config.py` (per HE1 PR #69 evidence). This is the canonical path.

Action: HE2 will keep `services/` location (avoiding mid-stream module relocations) and provide a `get_active_a1_horizons()` helper as an alias if helpful. Alternatively, the existing `get_horizon_config().active_horizons` is the equivalent API.
