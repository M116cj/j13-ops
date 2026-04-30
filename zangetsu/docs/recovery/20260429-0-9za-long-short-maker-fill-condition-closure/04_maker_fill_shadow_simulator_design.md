# 04 — Maker-Fill SHADOW Simulator Design

## Status

**DESIGN-ONLY.** No simulator code is built, executed, or persisted under 0-9ZA. The design below specifies what *would* be required to produce empirical LONG / SHORT / COMBINED maker-fill bps and is presented as a blueprint for the next-order recommendation (`0-9ZB-EXECUTION-ARCHITECTURE-SCOPING` if path proceeds).

## Architecture

Isolated read-only Python module. **NOT** linked into runtime; lives under `docs/recovery/.../analysis_scripts/maker_fill_sim/` if/when implemented. **No** import path from `services/` or `engine/` to it. **No** DB write permissions on the zangetsu DB; reads from `akasha-postgres` (katen tables) and `deploy-postgres-1` (champion lists) only.

```
                 ┌─────────────────────────────┐
                 │  zangetsu signal replay     │
                 │  (alpha + cuda_backtest as  │
                 │   pure functions, no DB)    │
                 └──────────┬──────────────────┘
                            │ signals (1=long, -1=short)
                            ▼
                 ┌─────────────────────────────┐
                 │  maker-fill simulator       │
                 │  - Side-aware bid/ask choice│
                 │  - Fill detection           │
                 │  - Queue haircut            │
                 │  - Adverse-selection drift  │
                 │  - Funding by side          │
                 └──────────┬──────────────────┘
                            │ filled[], adverse[], funding[]
                            ▼
                 ┌─────────────────────────────┐
                 │  per-side aggregator        │
                 │  → LONG / SHORT / COMBINED  │
                 │  → write JSONL to evidence/ │
                 └─────────────────────────────┘
```

## Core simulator logic

### LONG entry (post limit BUY at bid or bid - offset)

```
on signal[t]==+1:
    limit_price = bid[t] - limit_offset_bps * mid[t] / 1e4
    place_at_t  = t
    deadline    = t + max_wait_bars

    for u in (t, ..., deadline]:
        if low[u] <= limit_price:        # OHLCV proxy fill flag
            fill_t = u
            fill_p = limit_price
            apply queue_haircut(...)
            measure adverse[fill_t .. fill_t + adverse_window_bars]
            break
    else:
        record missed_fill(reason=expired)
```

### SHORT entry (post limit SELL at ask or ask + offset)

```
on signal[t]==-1:
    limit_price = ask[t] + limit_offset_bps * mid[t] / 1e4
    same fill loop using high[u] >= limit_price
```

### LONG exit / SHORT exit

Mirror logic, side-flipped. Exit can fall back to taker if `fallback_taker_exit=True` (scenario analysis only; **not** allowed for base PATH_A_GO claim).

## Required parameters

| Parameter | Description | Default (conservative) |
|-----------|-------------|------------------------|
| `limit_offset_bps` | distance inside spread (positive = inside, towards mid; negative = outside) | 0 (post at exact bid/ask) |
| `max_wait_bars` | max bars before missed fill | 1 (single bar at zangetsu's 5-min cadence) |
| `queue_haircut` | penalty for not being first in queue | 0.5 (assume only 50% chance fill executes when bar touches limit) |
| `fill_probability_model` | empirical or proxy | OHLCV-touch with `queue_haircut` |
| `adverse_window_bars` | bars after fill to measure adverse drift | 3 (15 min at 5-min bars) |
| `fallback_taker_exit` | allow taker exit on missed maker exit | False (scenario only) |
| `funding_model` | side-aware funding | per-bar funding rate × position direction × hold_bars / bars_per_8h |
| `fee_model` | maker/taker by tier | from `cost_model.py` (maker_bps for filled, taker_bps for fallbacks) |
| `spread_model` | symbol/time-aware spread | from `katen_tick_features.spread_bps` (Stable only); literature 1.5× spread for Diversified, 2× for High-Vol |

## Required output metrics (per the order's required table)

For each (champion, symbol, side ∈ {LONG, SHORT}) cell:

| Metric | Definition |
|--------|-----------|
| attempted maker entries | count of signal generation events |
| filled entries | count where fill predicate true within `max_wait_bars` |
| missed entries | attempted − filled |
| fill rate | filled / attempted |
| median fill delay | bars between signal and fill (filled set) |
| p90 fill delay | 90th pct of fill delay |
| adverse selection bps | mean (mid[fill+adverse_window] − fill_price) × side × 1e4 / fill_price |
| maker fee bps | from cost_model.maker_bps × 2 |
| funding bps | per-side funding contribution over hold |
| final net bps | gross − fees − funding − adverse − missed-opportunity-cost |
| A2 trade count after missed fills | filled count, compared against A2_MIN_TRADES=25 floor |

## Hard isolation rules

| Rule | Status |
|------|--------|
| Simulator must not write to zangetsu DB | enforced by separate connection string with `zangetsu_reports_ro` user (read-only role exists per `\l`) |
| Simulator must not place orders | no exchange client imported; no API key wired |
| Simulator must not modify `cuda_backtest.py` or `alpha_signal.py` | call them as pure functions through a thin adapter |
| Simulator output must live under `docs/recovery/.../*.jsonl` | enforced by hardcoded write path |
| Simulator must be runnable without runtime workers | no shared worker pool, no event_queue |

## What this design CANNOT do under 0-9ZA constraints

1. **Cannot consume raw bid/ask history** — `katen_raw_ticks` is empty (Phase 3). Simulator falls back to OHLCV high/low touch + `katen_tick_features` aggregated `spread_bps` for Stable tier only.
2. **Cannot empirically estimate queue position** — no top-of-book size history. Must use a literature-prior `queue_haircut` (default 0.5).
3. **Cannot cover Diversified or High-Vol tiers empirically** — Katen does not collect those symbols. Falls back to literature spread multipliers (1.5× / 2× Stable).
4. **Cannot cross-validate against real maker fills** — no historical maker-fill record to calibrate against (no `paper_trades`, no `trade_journal`, no live key).
5. **Cannot produce decisive PATH_A_GO** — even when implemented, the simulator's output is *one* conservative simulation of one chosen `queue_haircut` × `adverse_window` × `limit_offset` parameter set; without empirical fill data to anchor those parameters, the verdict band (Phase 5/6) remains wide enough that GO/NO_GO sits inside the noise.

## Conclusion

The simulator design is **buildable** in scope (~300 LOC Python + numpy, ~1-2 days engineering) **as a separate offline tool**. But its evidentiary value at HEAD `3cb5e08f` is bounded by the data gaps in Phase 3 — it would be a literature-prior amplifier, not an empirical validator.

