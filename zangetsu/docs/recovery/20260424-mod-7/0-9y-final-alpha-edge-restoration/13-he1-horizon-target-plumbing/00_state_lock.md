# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-HE1-HORIZON-TARGET-PLUMBING
**Date**: 2026-04-28
**Phase**: 0 / 7

## Git
- Branch: `main`
- HEAD: `986932df3f1c2c1b0c3736e98013f7bcbdc18ea6` (post-TF4, signed ED25519)
- origin/main: `986932df3f1c2c1b0c3736e98013f7bcbdc18ea6` ✅ in-sync
- Working tree (zangetsu): only runtime logs (`engine.jsonl.1` / calcifer state) — no source dirty.

## TF stack present
| Module | Path | Status |
|---|---|---|
| TF2 helper | `zangetsu/services/signal_aggregation.py` | ✓ |
| TF3 shadow | `zangetsu/services/tf3_shadow.py` | ✓ |
| TF4 production config | `zangetsu/services/aggregation_config.py` | ✓ |

## TF stack tests (regression)
```
pytest -q test_signal_aggregation.py test_tf3_shadow.py test_tf4_aggregation_config.py
→ 29 passed in 0.17s ✅
```

## TF stack OFF default verification
- 20 most-recent `arena_batch_metrics` events: **0 / 20** with `shadow_profiles` (TF3 OFF) and **0 / 20** with `aggregation_mode` (TF4 OFF) ✅
- Live worker env: no `ARENA_TF3_SHADOW`, no `ARENA_AGGREGATION_*` set → confirmed baseline mode
- Latest batch timestamp: 2026-04-28T18:25:59Z (live A1 producing baseline batches)

## Existing horizon mechanism
| Location | Code |
|---|---|
| `engine/components/alpha_engine.py:890` | `def _forward_returns(close: np.ndarray) -> np.ndarray` (static method) |
| `engine/components/alpha_engine.py:894` | `horizon = max(1, int(_os.environ.get('ALPHA_FORWARD_HORIZON', '60')))` |
| `engine/components/alpha_engine.py:930, 976` | `forward_returns = self._forward_returns(close)` (called inside `evolve()`) |
| `engine/components/alpha_engine.py:1062` | `alpha_hash = hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]` (formula-only) |

**Current state**: A1 reads `ALPHA_FORWARD_HORIZON` env (default 60) on every `_forward_returns` call. Horizon is global per worker process. `alpha_hash` is formula-only (does NOT distinguish horizons).

**Pre-HE1 baseline**: single horizon = **60 bars**.

## Telemetry sanity
- UNKNOWN_REJECT total: **0** ✅
- COUNTER_INCONSISTENCY total: **0** ✅
- Conservation residual: **0** ✅

## OP1/TF2/TF3/TF4 status
| Order | Status |
|---|---|
| OP1 | COMPLETE (`82056123`) |
| TF2 | COMPLETE (`3decabd4`) |
| TF3 | COMPLETE (`0cef908d`) |
| TF4 | COMPLETE (`986932df`) |

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Any regression detected | ❌ no — 29 PASS module tests, 20/20 baseline batches clean |
| TF4 integration unstable | ❌ no — config defaults OFF |
| Aggregation OFF path differs | ❌ no — verified via direct config check + live worker env |
| A1 not running | ❌ no — live batches at 2026-04-28T18:25:59Z |
| Telemetry not clean | ❌ no — UR=0, CI=0, residual=0 |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.

## Recorded baseline metric snapshot (for Phase 4 verification)
- `ALPHA_FORWARD_HORIZON` env (production): unset → resolves to **60** (default)
- Recent batches: produced at `latest_ts = 2026-04-28T18:25:59Z`
- Active workers: 4 × arena_pipeline + arena23 + arena45 + calcifer supervisor
