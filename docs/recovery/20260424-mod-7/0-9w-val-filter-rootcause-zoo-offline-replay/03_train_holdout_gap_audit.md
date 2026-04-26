# 03 — Train vs Holdout Gap Audit

## 1. Constants

| Field | Value | Source |
| --- | --- | --- |
| `TRAIN_SPLIT_RATIO` | 0.7 | `arena_pipeline.py:283` |
| Split formula | `split = int(w * 0.7)` | `arena_pipeline.py:508` |

## 2. Actual Time Windows (read from parquet files)

| Symbol | Train start | Train end | Holdout start | Holdout end | Train bars | Holdout bars |
| --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT | 2019-09-18 | 2024-05-02 | 2024-05-02 | 2026-04-26 | 2 431 800 | 1 042 200 |
| XRPUSDT | 2020-01-06 | 2024-06-04 | 2024-06-04 | 2026-04-26 | 2 320 570 | 994 530 |
| 1000PEPEUSDT | 2023-05-09 | 2025-06-05 | 2025-06-05 | 2026-04-26 | 1 092 168 | 468 073 |

(Same 0.7 split applied to all 14 symbols.)

## 3. Crypto Regime Coverage

| Period | Coverage in train? | Coverage in holdout? | Notable events |
| --- | --- | --- | --- |
| 2019-2020 | YES (BTC, XRP, BNB, etc.) | NO | DeFi summer, COVID crash |
| 2021 bull | YES | NO | All-time-highs |
| 2022 bear | YES | NO | LUNA, FTX collapse |
| 2023 H2 | YES | NO | Recovery |
| 2024 Jan-Apr | YES | NO | BTC ETF approval, halving |
| 2024 May-Dec | NO | **YES** | Post-ETF, election rally |
| 2025 | NO | **YES** | Trump-era new highs |
| 2026 Jan-Apr | NO | **YES** | Recent / current |

→ **Train spans the full 2019-2024 history including all major regimes**. **Holdout spans only 2024-05 → 2026-04** — a structurally distinct era characterized by post-ETF / election / new-highs / institutional dynamics. The two distributions are not iid.

## 4. Symbol/Regime Mapping (regime tags from live A1 logs)

| Regime tag | Active symbols (recent obs) |
| --- | --- |
| BULL_TREND | BTC, ETH, BNB, AVAX, 1000SHIB, 1000PEPE, GALA, FIL, LINK, DOT |
| BEAR_RALLY | SOL, AAVE |
| CONSOLIDATION | XRP |
| (other regimes appear sporadically) |  |

## 5. Train vs Holdout Macro Statistics

Without running a full statistical comparison (read-only, no code patches), the following observations from market structure are documented:

| Metric (qualitative) | Train | Holdout |
| --- | --- | --- |
| Volatility character | mixed (calm + crashes + rallies) | predominantly trending up with sharp drawdowns |
| Funding regime | bear-funding common (2022) | mostly positive funding |
| ETF / institutional inflow | absent | **present** |
| Halving cycle position | pre-halving in train end | post-halving in holdout |
| Macro USD strength | rising (2022) → falling (2024) | post-2024-Q4 USD strength |

Crypto markets in the holdout window have qualitatively different drivers than the train window. Even without numerical comparison, this is a high-likelihood regime drift candidate.

## 6. Does Split Cross a Structural Break?

| Test | Result |
| --- | --- |
| Split timestamp 2024-05-02 (BTC) | **YES** — falls between BTC ETF approval (Jan 2024) and halving (Apr 2024); the period immediately after is structurally different (ETF flows, institutional rebalance) |
| Holdout dominated by post-halving + Trump rally + 2025 cycle | YES (24 months of holdout is enough to manifest these regime effects) |
| Cross-validation on multiple windows attempted? | NO (single fixed split per symbol) |

## 7. Phase 3 Classification

Per order §16:

| Verdict | Match? |
| --- | --- |
| VALID_OOS_FAILURE_LIKELY | partial — val_neg_pnl is a legitimate gate, but pre-Phase-7 we cannot yet say whether it's the formula's fault or the data's |
| **REGIME_DRIFT_LIKELY** | **YES — high probability based on qualitative macro coverage gap** |
| SPLIT_ARTIFACT_LIKELY | partial — 0.7 ratio + 4.5y train / 2y holdout is a defensible engineering choice but creates a known regime-shift boundary |
| DATA_WINDOW_DEFECT_LIKELY | NO (data is real OHLCV; not corrupted) |
| INSUFFICIENT_EVIDENCE | partial — Phase 7 offline replay is needed to confirm whether ALL formulas fail (regime) or just GP-evolved ones (overfit) |

→ **Phase 3 verdict: REGIME_DRIFT_LIKELY** with note that the 2024-05 split timing places the boundary right at the BTC-ETF / halving regime change. This is a primary suspect, but Phase 7 will discriminate between "regime drift" and "deeper systemic" causes.
