## v0.1.0 — 2026-04-20 — Initial J01 strategy project (harmonic K=2)

**Scope:** strategy project on top of Zangetsu engine v0.7.0.

- `fitness.py` — sign-gated, epsilon-floored harmonic mean of IC over
  two halves of the training window. Magnitude floor `MIN_ABS_IC = 5e-3`,
  epsilon `1e-6`, height penalty `1e-3` per tree-height unit.
- `config/thresholds.py` — A2 `trades>=25, pnl>0`; A3 `5 segments, >=4/5
  WR>0.45 AND pnl>0`; A4 `training regime WR>0.40 AND >=1 other regime
  WR>0.40`; A5 `14-day live paper-trade shadow, WR>0.45, pnl>0,
  max_consecutive_neg_days<3`; `ALPHA_FORWARD_HORIZON=60 bars`,
  `COST_BPS=5.0`.
- `config/sql/j01_status_view.sql` — §17.1 VIEW (DB-side canonical).
- `scripts/rescan_j01_legacy.py` — will be added when legacy rescan
  under J01 specifically is required (current legacy pool was rescanned
  under the now-removed v0.6.0 formula; all rejected and will not be
  retried under J01).

**Bootstrapped from:** Zangetsu engine v0.7.0 (which split the
monolith into engine + strategies).
