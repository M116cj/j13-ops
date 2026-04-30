# 01 — Fee Tier / Account Verification

## Mode

READ-ONLY / DECISION-ONLY. **Zero** Binance API calls executed during 0-9ZA. No production trading key requested or used (STOP-2 enforced).

## Required questions and answers

| # | Question | Answer | Evidence / Status |
|---|----------|--------|-------------------|
| 1 | Current exchange? | **Binance Futures (USDⓈ-M)** | `cost_model.py` header + symbol set (`*USDT` perpetuals) |
| 2 | Current fee tier? | **DATA_BLOCKED** | No `BINANCE_API_KEY` available in 0-9ZA scope; account-level call to `GET /fapi/v1/account` not permitted under READ-ONLY scope without prior j13 authorization for live key usage. |
| 3 | Current maker fee? | **assumed 2.0 / 2.5 / 4.0 bps** (Stable / Diversified / High-Vol) per `config/cost_model.py` `SymbolCost.maker_bps` | maker_bps is **DEAD DATA** — defined but never consumed by `total_round_trip_bps` (taker-only formula). |
| 4 | Current taker fee? | **5.0 / 6.25 / 10.0 bps** (Stable / Diversified / High-Vol) | `config/cost_model.py:46-66` |
| 5 | Current 30-day volume? | **DATA_BLOCKED** | No paper / live trade record in DB (`paper_trades=0`, `trade_journal=0`). No live exec layer to derive volume from. |
| 6 | VIP3 requirement? | **≥ $100M / 30d notional** (Binance Futures public schedule, 2026 Q1) | secondary literature; primary verification deferred to live API call (not run). |
| 7 | Gap to VIP3? | **DATA_BLOCKED** (Q5 unknown) | derived blocker. |
| 8 | Is volume growth feasible? | **NO under current architecture** | ZANGETSU has 0 deployable champions; no live execution; no organic 30d volume to grow. Reaching $100M/30d would require ≈3.3M$/day notional — far beyond current capital allocation discussed in 0-9Z. |
| 9 | Institutional sub-account / broker tier possible? | **EXTERNAL_ONLY** | Outside zangetsu's scope; capital intervention by j13 required (account-tier sponsorship, broker subaccount, Binance institutional desk). |
| 10 | Can fee tier alone reduce cost from 14.5 bps → ≤ 9.4 bps? | **No (VIP1 / VIP2 insufficient); only VIP3+ reaches 35% cut** | 0-9Z `02_fee_venue_tier_matrix.md` evidence carried forward. |

## Cost / scenario matrix

> Carried forward from 0-9Z `02_fee_venue_tier_matrix.md` and re-stated here for AC compliance. Funding (1.0 bps round-trip) and slippage (Diversified-tier 1.0 bps) held constant per current model. Effective bps = `(maker × 2 or taker × 2) + slippage + funding`.

| Scenario | Maker bps | Taker bps | Round-trip taker bps | Funding bps | Slippage bps | Effective bps (taker) | Cost cut vs Diversified taker (14.5) | Verdict |
|----------|----------:|----------:|----------------------:|------------:|-------------:|----------------------:|-------------------------------------:|---------|
| Current tier (Diversified taker) | 2.5 | 6.25 | 12.5 | 1.0 | 1.0 | **14.5** | 0% | baseline |
| VIP1 (taker only) | 2.0 | 5.0 | 10.0 | 1.0 | 1.0 | **12.0** | -17% | INSUFFICIENT |
| VIP2 (taker only) | 1.6 | 4.0 | 8.0 | 1.0 | 1.0 | **10.0** | -31% | BORDERLINE |
| VIP3 (taker only) | 1.4 | 3.5 | 7.0 | 1.0 | 1.0 | **9.0** | -38% | SUFFICIENT (just) |
| VIP4+ (taker only) | 1.2 | 3.0 | 6.0 | 1.0 | 1.0 | **8.0** | -45% | SUFFICIENT |
| Maker-only current tier | 2.5 | — | (5.0 maker round-trip) | 1.0 | 1.0 | **7.0** (theoretical) | -52% | SUFFICIENT theoretical |
| Maker-only VIP3 | 1.4 | — | (2.8 maker round-trip) | 1.0 | 1.0 | **4.8** (theoretical) | -67% | SUFFICIENT theoretical |

> All "maker-only" rows assume **100% fill at quoted price with zero adverse selection** — none of which is empirically validated. Real maker-only effective cost = `(maker × 2) + slippage + funding + adverse_selection_bps` where `adverse_selection_bps ∈ [1.8, 4.2]` per literature mid-band (0-9Z `03_maker_only_feasibility.md`).

## VIP3 feasibility verdict

**`VIP3_DATA_BLOCKED` (with strong negative prior)**

- Primary blocker: cannot verify current 30d volume without API key access (j13 authorization required for any live key handling).
- Secondary blocker: even if verified, `paper_trades=0` and `trade_journal=0` → no zangetsu-generated organic volume exists. Reaching VIP3 organically is structurally impossible under current `deployable_count = 0` state.
- Path forward: only `VIP3_EXTERNAL_ONLY` (broker / sub-account / institutional sponsorship by j13) is operationally viable; this falls outside zangetsu's automated path.

## Forbidden-touch audit (Phase 1)

| Forbidden item | Touched? |
|----------------|----------|
| live order placement | ❌ |
| production trading key usage | ❌ |
| `cost_model.py` modification | ❌ |
| Arena threshold change | ❌ |
| `A2_MIN_TRADES` change | ❌ |
| Champion promotion change | ❌ |
| `deployable_count` semantic change | ❌ |
| DB write | ❌ |

## Phase 1 conclusion

Fee-tier alone **cannot** reach the 35% break-even cost cut without VIP3+, and VIP3 reachability is `DATA_BLOCKED` (no API key, no organic volume). This forces the path-forward burden onto either (a) maker-only execution or (b) external account sponsorship — both of which fall outside zangetsu's scope and outside 0-9ZA's permitted simulation surface.

