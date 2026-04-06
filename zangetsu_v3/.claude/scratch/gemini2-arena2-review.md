# Arena 2 Compression Review — 2026-04-06

## 3 HIGH Findings (fix before production)

### 1. Single-Symbol Evaluation — BTC Bias
**Severity: HIGH**
- compress() picks first symbol only (BTCUSDT) for all correlation calculations
- Factors strong on ETH but weak on BTC get dropped
- Fix: Average correlations across all symbols

### 2. id()-Based Index Remapping Fragility
**Severity: HIGH**
- After remove_weak_candidates, filtered_series rebuilt using id(cand)
- Breaks silently if function ever creates new dicts
- Fix: Use stable identifier (expression + loss + regime tuple)

### 3. Hardcoded DB Credentials
**Severity: HIGH (Security)**
- DB_DSN contains plaintext password on line 39
- Fix: Load from environment variables

## MEDIUM Findings

| # | Finding |
|---|---------|
| 4 | Pearson-only for target correlation (misses non-linear) |
| 5 | Weak threshold 0.01 is effectively a no-op |
| 6 | No segment-based eval despite docstring claim |
| 7 | NaN subset mismatch in pairwise correlation |
| 8 | Greedy dedup has no secondary sort key |
| 9 | Test coverage gaps (threshold mismatch, no id() test) |

## LOW Findings
| 10 | Data leakage — no train/holdout split in compression |
| 12 | Cache key hash collision risk |
