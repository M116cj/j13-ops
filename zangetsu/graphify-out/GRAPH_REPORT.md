# Graph Report - .  (2026-04-17)

## Corpus Check
- 79 files · ~79,658 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1228 nodes · 2898 edges · 31 communities detected
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 1142 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 80 edges
2. `CostModel` - 78 edges
3. `StructuredLogger` - 69 edges
4. `Backtester` - 66 edges
5. `range()` - 66 edges
6. `PipelineDB` - 45 edges
7. `BacktestResult` - 40 edges
8. `main()` - 39 edges
9. `IndicatorCompute` - 37 edges
10. `HealthMonitor` - 37 edges

## Surprising Connections (you probably didn't know these)
- `Apply the TP strategy specified in passport. Returns modified signals.` --uses--> `BacktestResult`  [INFERRED]
  services/shared_utils.py → engine/components/backtester.py
- `Compute indicator values from passport configs using Rust engine.` --uses--> `BacktestResult`  [INFERRED]
  services/shared_utils.py → engine/components/backtester.py
- `Extract Arena 3 parameters from passport for faithful replay in A4/A5.      Retu` --uses--> `BacktestResult`  [INFERRED]
  services/shared_utils.py → engine/components/backtester.py
- `Check if DB connection is alive, reconnect if not. Returns (connection, reconnec` --uses--> `BacktestResult`  [INFERRED]
  services/shared_utils.py → engine/components/backtester.py
- `Reset champions stuck in *_PROCESSING status past their lease expiry.      Run p` --uses--> `BacktestResult`  [INFERRED]
  services/shared_utils.py → engine/components/backtester.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (118): Arena 13 — Downstream Truth Feedback Controller.  Converts A3/A4/A5 outcome data, Extract downstream truth and compute guidance weights., _a2_stage2_pairs(), compute_trade_stats(), is_duplicate_champion(), main(), pick_champion(), process_arena2() (+110 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (80): compute_guidance(), determine_mode(), load_gating_policy(), main(), arena4_fail(), arena4_pass(), backtest_slice(), check_daily_reset() (+72 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (56): create_dashboard_app(), backfill_symbol(), fetch_klines(), main(), fetch_funding_rate(), fetch_open_interest(), main(), Fetch Binance Futures funding rate and open interest history → parquet.  Usage: (+48 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (65): Enum, Async trade journal backed by PostgreSQL.      Usage:         journal = TradeJou, db: a PipelineDB instance (engine.components.db)., Fetch the N most recent trade records., Generate a summary for a given date (default: today UTC).          Returns: {dat, TradeJournal, ChampionPassport, Champion passport — progressive JSONB enrichment per arena. (+57 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (68): compute_ao(), compute_cci(), compute_chande_forecast(), compute_cmo(), compute_dpo(), compute_elder_bear(), compute_elder_bull(), compute_kst() (+60 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (51): Process a single completed 1m bar.          Flow:           1. Update regime lab, compute_ema(), compute_rsi(), compute_sma(), dispatch(), forward_fill(), mtf_adx(), mtf_atr() (+43 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (63): compute_bollinger_bw(), compute_cumulative_funding(), compute_funding_zscore(), compute_garman_klass(), compute_log_returns(), compute_normalized_atr(), compute_normalized_range(), compute_oi_change() (+55 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (59): _ema(), _env_int(), main(), _optimal_k(), _optimal_size(), sample_diverse_indicators(), weighted_sample(), BacktestResult (+51 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (34): CardRotator, Card rotation — hot-swap deployed cards when Arena 5 ELO #1 changes.  When a DEP, Three-phase rotation: stop entries -> wait flat -> swap.          Returns True i, Check if card has no open positions (via paper_trades table)., Persist rotation event to rotation_log., Dashboard hook: rotation status., Record of a pending or completed rotation., Monitors ELO rankings and rotates deployed cards when #1 changes.      Uses asyn (+26 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (48): AdaptiveScorer, Adaptive family-level scoring for Zangetsu V9 Sharpe Quant doctrine.  Score_t(f), Score a single family. Returns 0-100., Score all families, return sorted by adaptive_score descending., Smoothly adjust benchmark upward from certified family scores., Wilson lower-bound confidence interval for win rate., Sigmoid mapping for normalizing metrics to [0,1]., Family-level adaptive scorer combining geometric + weighted-average blending. (+40 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (38): bloom_add(), bloom_bulk_add(), bloom_check(), bloom_close(), bloom_count(), bloom_init(), _hashes(), LocalBloomFilter (+30 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (37): adx(), adxr(), apo(), aroon_down(), aroon_oscillator(), aroon_up(), bars_since_highest(), bars_since_lowest() (+29 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (15): AlphaEngine, AlphaResult, V9 GP Alpha Expression Engine — Genetic Programming for alpha factor discovery., A discovered alpha expression with its metrics., Genetic Programming engine for evolving alpha expressions., Define the GP primitive set., Information Coefficient = rank correlation between alpha and forward returns., Evaluate a GP individual. Returns (fitness,) tuple. (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.17
Nodes (25): ad(), amihud_illiq(), clv(), cmf(), dispatch(), ema_vec(), eom(), force_index() (+17 more)

### Community 14 - "Community 14"
Cohesion: 0.14
Nodes (20): collect_all(), collect_symbol(), fetch_funding_rate(), fetch_open_interest(), _init_exchange(), _load_existing(), merge_funding_to_1m(), merge_oi_to_1m() (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (15): compute_signal_strength(), grade_multiplier(), indicator_vote(), _mean_rev_signal(), _ob_os_signal(), Shared signal generation — V9 Semantic Continuous Signals. Indicator-specific in, V9: Continuous momentum-based voting for trending regimes.     Output: continuou, V9: Vote based on indicator values. Returns continuous [-1, +1] strength. (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (13): classifyParam(), fetchCosts(), fetchHealth(), fetchParams(), flattenObj(), renderArenas(), renderCosts(), renderHealth() (+5 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (8): AttentionAggregator, IndicatorAttention, V9 Attention-based Signal Aggregation.  Replaces majority voting with learned se, Aggregate indicator signals to single signal array.          indicator_signals:, Self-attention over indicator signals + market state conditioning., indicator_signals: (batch, n_indicators) in [-1, +1]             regime_idx: (ba, Lightweight numpy implementation for live deployment.      Takes learned attenti, weights: array of shape (n_indicators,) — stored attention weights         regim

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (3): _Health, MinimalEngine, Apply runtime overrides. Returns list of changed field names.

### Community 19 - "Community 19"
Cohesion: 0.29
Nodes (12): basis_spread(), dispatch(), funding_predicted(), funding_rate(), funding_velocity(), liquidation_volume(), long_short_ratio(), oi_concentration() (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.29
Nodes (12): alt_rotation(), btc_correlation(), btc_dominance(), defi_tvl_change(), difficulty_roc(), dispatch(), eth_correlation(), gas_price_norm() (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.21
Nodes (11): bonferroni_threshold(), compute_p_value(), compute_pnl_p_value(), is_significant(), load_baseline(), P-value computation against random baseline distribution.  Computes the probabil, Is this p-value significant after Bonferroni correction?, Load random baseline statistics. Cached after first load. (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.22
Nodes (9): accelerate_df(), benchmark_vs_cpu(), V9 GPU Acceleration Wrapper.  Optional cuDF-accelerated operations. All function, Convert pandas DataFrame or polars DataFrame to cuDF if GPU available., Rolling mean on GPU if available, else numpy., Rolling std on GPU if available., Quick benchmark: GPU vs CPU for rolling operations., rolling_mean_gpu() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.29
Nodes (6): compute_indicator(), _load_module(), MockConfig, OBSOLETE — V5-era tests, references removed modules (voter, data_weight). Marked, Load a single .py file as a module, bypassing package __init__., VoterConfig

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Arena 13 Evolution — DISABLED.  Status: Non-functional stub. Requires full reimp

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Total cost for entry + exit (taker both sides) + avg funding.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Return a fallback aggregator that behaves like majority voting.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Causal EMA computation.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Currently in-progress rotations by regime.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **257 isolated node(s):** `Per-symbol cost model: taker fees, funding rates, slippage estimates.  Costs var`, `Cost parameters for a single trading pair.`, `Total cost for entry + exit (taker both sides) + avg funding.`, `Runtime cost model. Supports per-symbol overrides from console.      Usage:`, `Return cost for symbol, or a conservative default.` (+252 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 24`** (2 nodes): `Arena 13 Evolution — DISABLED.  Status: Non-functional stub. Requires full reimp`, `arena13_evolution.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Total cost for entry + exit (taker both sides) + avg funding.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Return a fallback aggregator that behaves like majority voting.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Causal EMA computation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Currently in-progress rotations by regime.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `verify_ohlcv.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 6`, `Community 8`, `Community 14`, `Community 21`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `range()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 5`, `Community 7`, `Community 10`, `Community 12`, `Community 15`, `Community 22`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `compute()` connect `Community 0` to `Community 1`, `Community 2`, `Community 23`, `Community 7`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 76 inferred relationships involving `Settings` (e.g. with `Console module — FastAPI endpoints for runtime parameter tuning.` and `BloomFilter`) actually correct?**
  _`Settings` has 76 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `CostModel` (e.g. with `Console module — FastAPI endpoints for runtime parameter tuning.` and `BloomFilter`) actually correct?**
  _`CostModel` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `StructuredLogger` (e.g. with `BloomFilter` and `Arena Pipeline V9 — High-throughput optimized A1 with bloom filter dedup + A2 pr`) actually correct?**
  _`StructuredLogger` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `Backtester` (e.g. with `BloomFilter` and `Arena Pipeline V9 — High-throughput optimized A1 with bloom filter dedup + A2 pr`) actually correct?**
  _`Backtester` has 60 INFERRED edges - model-reasoned connections that need verification._