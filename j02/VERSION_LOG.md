## v0.1.0 — 2026-04-20 — Initial J02 strategy project (ICIR K=5)

**Scope:** strategy project on top of Zangetsu engine v0.7.0.

- `fitness.py` — ICIR-style `mean(|IC_k|) - lambda*std(|IC_k|)` over K=5
  contiguous folds. `LAMBDA_STD=1.0`, `MIN_ABS_IC=3e-3` per fold,
  `MIN_FOLD_BARS=100`, sign-agreement required across all 5 folds.
- `config/thresholds.py` — matches J01 for A2/A3/A4/A5 thresholds
  initially; diverge later per observed behavior. `ALPHA_FORWARD_HORIZON=60`,
  `COST_BPS=5.0`.
- `config/sql/j02_status_view.sql` — §17.1 VIEW.
- Deflated Sharpe Ratio post-hoc filter for A5 live-proven promotion is
  **v0.2.0 roadmap** — not implemented in v0.1.0 (would block initial
  bring-up and contradict "first DEPLOYABLE today" pragmatism).

**Bootstrapped from:** Zangetsu engine v0.7.0.
