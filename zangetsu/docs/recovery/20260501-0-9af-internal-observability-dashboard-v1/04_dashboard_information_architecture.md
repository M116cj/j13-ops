# 04 — Information Architecture

**ORDER**: 0-9AF — Phase 2

## Page Tree

```
Landing (app.py)
├─ 01 Overview
├─ 02 Core Factory
├─ 03 Arena A1
├─ 04 Arena A2
├─ 05 Arena A3 (NOT_AVAILABLE in shadow)
├─ 06 Candidates (filterable explorer)
├─ 07 Survivors (PASSED + near-survivors strictly separated)
├─ 08 Rejects
├─ 09 Feedback (feedback_weights + next_batch_weights)
└─ 10 System Health (per-source freshness + parser state)
```

Streamlit auto-discovers pages from `zangetsu/dashboard/pages/NN_*.py` files.

## Code Layout

```
zangetsu/dashboard/
├── __init__.py            (lazy FastAPI re-export; coexists with legacy code)
├── app.py                 (landing page)
├── config.py              (paths, port, refresh, freshness thresholds)
├── data_sources/
│   ├── parsers.py         (parse_jsonl / parse_csv / parse_json + state)
│   ├── runtime_health.py  (freshness_for + state semantics)
│   └── batch_artifacts.py (load_latest_batch / load_batch_from_folder)
├── view_models/
│   ├── overview.py
│   ├── arenas.py          (build_a1 / build_a2 / build_a3)
│   ├── candidates.py
│   ├── survivors.py
│   ├── feedback.py
│   └── health.py
├── components/
│   ├── freshness_badge.py
│   └── charts.py          (funnel / bar_top_n / status_donut / reject_reason_stacked)
└── pages/
    ├── 01_Overview.py
    ├── 02_Core_Factory.py
    ├── 03_Arena_A1.py
    ├── 04_Arena_A2.py
    ├── 05_Arena_A3.py
    ├── 06_Candidates.py
    ├── 07_Survivors.py
    ├── 08_Rejects.py
    ├── 09_Feedback.py
    └── 10_System_Health.py
```

Layered: pages → view_models → data_sources → file system. View models are pure functions; pages are thin Streamlit shells. This is what makes `tests/dashboard/test_view_models.py` possible without a Streamlit context.
