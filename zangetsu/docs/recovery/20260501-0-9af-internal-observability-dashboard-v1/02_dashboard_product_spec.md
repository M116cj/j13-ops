# 02 — Dashboard Product Spec

**ORDER**: 0-9AF — Phase 2

## Operator Workflow

The owner opens `http://127.0.0.1:8785/` over SSH tunnel or Tailscale, lands on the Overview page, and answers the operator questions in §1 of the order:

| Question | Page | Source |
|---|---|---|
| What is the system doing now? | Overview | run_summary.json + status counts |
| Is mining running correctly? | System Health | per-source freshness state |
| What happened in latest batch? | Overview, Core Factory | run_summary, manifest, results |
| What is happening in A1 / A2 / A3? | Arena pages | shadow_batch_results status field |
| Why are candidates dying? | Rejects | reject_reason distribution |
| What survived? | Survivors | survivor_report.csv |
| What almost survived? | Survivors | near_survivor_report.csv |
| What should the next batch focus on? | Feedback | next_batch_weights.json |
| Is the system fresh and trustworthy? | System Health | runtime_health.freshness_for |

## Interactions

- Sidebar navigates between 10 pages (Streamlit native).
- Candidate Explorer has 5 filters + 1 substring search.
- Survivors page strictly separates two tables.
- Feedback page exposes raw JSON via collapsible expanders.
- Health page shows per-source state table + summary banner.

## User Trust Guarantees

- Every page shows source path + freshness badge for the artifact it depends on.
- 'NO DATA' / 'MISSING' / 'NOT_AVAILABLE' / 'STALE' rendered as distinct states from numeric 0.
- A3 page shows NOT_AVAILABLE explicitly (not 0/0) since shadow orders never run A3.
