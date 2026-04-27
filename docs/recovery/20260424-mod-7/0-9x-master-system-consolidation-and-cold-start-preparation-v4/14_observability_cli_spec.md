# 42-14 — `zangetsu_obs` Observability CLI — Specification

**Order**: TEAM ORDER 0-9X-MASTER-SYSTEM-CONSOLIDATION-AND-COLD-START-PREPARATION-v4
**Track**: O — Observability CLI
**Date**: 2026-04-27
**Status**: DESIGN ONLY — DO NOT IMPLEMENT under this order
**Scope**: Single-binary CLI on Alaya producing one JSONL summary report covering 22 metrics.

---

## Invocation

```
zangetsu_obs                         # one-shot, JSONL to stdout
zangetsu_obs --pretty                # human-readable JSON
zangetsu_obs --metrics 1,2,3         # subset
zangetsu_obs --since 1h              # override default windows
zangetsu_obs --emit-prom             # also emit Prometheus textfile
```

Exit codes:
- `0`  GREEN
- `1`  YELLOW (≥1 yellow, no red)
- `2`  RED (≥1 red metric)
- `10` Inconclusive (DB/log unreachable)

---

## Output Contract

A single JSONL line per run on stdout. Fields:

```
{"ts":"<utc-iso>","run_id":"<uuid>","head":"<sha7>","overall":"GREEN|YELLOW|RED","metrics":[ {…22 entries…} ]}
```

Each metric entry:

```
{"id":<int>,"name":"<slug>","value":<scalar|object>,"status":"GREEN|YELLOW|RED|BLOCKED","source":"<short>","sampled_at":"<utc-iso>","note":"<optional>"}
```

`BLOCKED` is reserved for metrics whose source does not yet exist (Phase 4 DB
schema gap). Blocked metrics are emitted with `value:null` and a `note`
explaining what is missing.

---

## Metric Catalog — 22 Metrics

> File-paths are Alaya-relative (`/tmp/...`, `/home/j13/j13-ops/...`).
> All Postgres queries run against `deploy-postgres-1` (`j13ops` DB).

### 1. A1 alive (process count == 4)

- **Source**: `pgrep -af zangetsu_a1_w | wc -l` on Alaya
- **Threshold**:
  - GREEN: `count == 4`
  - YELLOW: `count == 3`
  - RED: `count <= 2`
- **Cadence**: every CLI run (default 5 min via cron caller)
- **Sample**: `{"id":1,"name":"a1_alive","value":4,"status":"GREEN","source":"pgrep","sampled_at":"2026-04-27T08:00:01Z"}`

### 2. A1 generated count (last 1h, last 24h)

- **Source**: `grep -c "GENERATED " /tmp/zangetsu_a1_w*.log` filtered by timestamp window; or DB `SELECT count(*) FROM arena_generated WHERE ts > now() - interval '1 hour'`
- **Threshold**:
  - GREEN: `1h_count >= 50` AND `24h_count >= 1500`
  - YELLOW: `1h_count >= 10`
  - RED: `1h_count == 0`
- **Cadence**: per run
- **Sample**: `{"id":2,"name":"a1_generated","value":{"h1":78,"h24":1842},"status":"GREEN","source":"a1_logs+arena_generated"}`

### 3. A1 rejection distribution (top-5 reasons, last 1h)

- **Source**: `grep "REJECTED" /tmp/zangetsu_a1_w*.log | awk -F'reason=' '{print $2}' | sort | uniq -c | sort -nr | head -5`
- **Threshold**:
  - GREEN: top reason is a known/expected reason (allowlist) AND no `UNKNOWN_REJECT`
  - YELLOW: any unexpected reason in top 5
  - RED: `UNKNOWN_REJECT` present (cross-checked with metric 16)
- **Cadence**: per run
- **Sample**: `{"id":3,"name":"a1_reject_top5","value":[{"reason":"INSUFFICIENT_HISTORY","count":312},{"reason":"FITNESS_BELOW_MIN","count":188}, ...],"status":"GREEN"}`

### 4. `train_pnl` distribution

- **Source**: `SELECT avg(train_pnl), percentile_cont(0.5) WITHIN GROUP (ORDER BY train_pnl) p50, percentile_cont(0.95) WITHIN GROUP (ORDER BY train_pnl) p95, stddev(train_pnl), count(*) FILTER (WHERE train_pnl > 0) FROM champion_pipeline_staging WHERE created_at > now() - interval '1 hour'`
- **Threshold**:
  - GREEN: `count_positive >= 1` AND `p95 > 0`
  - YELLOW: `count_positive == 0` AND `count >= 10`
  - RED: `count == 0` (nothing in window)
- **Cadence**: per run
- **Sample**: `{"id":4,"name":"train_pnl","value":{"mean":0.018,"p50":0.012,"p95":0.072,"std":0.045,"count_positive":31},"status":"GREEN"}`

### 5. `val_pnl` distribution

- **Source**: same query as #4, column `val_pnl`
- **Threshold**: as #4
- **Cadence**: per run
- **Sample**: `{"id":5,"name":"val_pnl","value":{"mean":0.005,"p50":0.003,"p95":0.041,"std":0.038,"count_positive":12},"status":"GREEN"}`

### 6. `combined_sharpe` distribution

- **Source**: same query, column `combined_sharpe`
- **Threshold**:
  - GREEN: `p95 >= 1.0` AND `count_positive >= 1`
  - YELLOW: `p95 >= 0.5`
  - RED: `p95 < 0.5` OR `count_positive == 0`
- **Cadence**: per run
- **Sample**: `{"id":6,"name":"combined_sharpe","value":{"mean":0.42,"p50":0.31,"p95":1.12,"std":0.51,"count_positive":18},"status":"GREEN"}`

### 7. Cross-symbol consistency distribution

- **Source**: `SELECT count(*) FILTER (WHERE positive_symbols >= 2) * 1.0 / NULLIF(count(*),0) FROM champion_pipeline_staging WHERE created_at > now() - interval '1 hour'`
- **Threshold**:
  - GREEN: `pct >= 0.40`
  - YELLOW: `pct >= 0.20`
  - RED: `pct < 0.20`
- **Cadence**: per run
- **Sample**: `{"id":7,"name":"cross_symbol_consistency","value":{"pct":0.47},"status":"GREEN"}`

### 8. Staging row count

- **Source**: `SELECT count(*) FROM champion_pipeline_staging`
- **Threshold**:
  - GREEN: `count >= 1`
  - YELLOW: `count == 0` AND `metric 2 (a1_generated h1) > 0`
  - RED: `count == 0` AND `metric 2 == 0` over last 24h
- **Cadence**: per run
- **Sample**: `{"id":8,"name":"staging_rows","value":1284,"status":"GREEN"}`

### 9. Fresh row count — **BLOCKED (Phase 4 schema gap)**

- **Source**: `SELECT count(*) FROM champion_pipeline_fresh` (table missing in Phase 4)
- **Status**: `BLOCKED` until schema migration lands
- **Note**: Emit `{"id":9,"name":"fresh_rows","value":null,"status":"BLOCKED","note":"champion_pipeline_fresh missing — Phase 4 schema migration pending"}`

### 10. Rejected row count

- **Source**: `SELECT count(*) FROM champion_pipeline_rejected WHERE rejected_at > now() - interval '1 hour'`
- **Threshold**:
  - GREEN: `count >= 0` (informational)
  - YELLOW: `count > 5 * staging_rows`
  - RED: `count > 0` AND `staging_rows == 0` (everything rejected)
- **Cadence**: per run
- **Sample**: `{"id":10,"name":"rejected_rows","value":47,"status":"GREEN"}`

### 11. `champion_pipeline` status distribution

- **Source**: `SELECT status, count(*) FROM champion_pipeline GROUP BY 1`
- **Threshold**:
  - GREEN: contains at least one of `DEPLOYABLE` / `LIVE`
  - YELLOW: only `STAGING` and `REJECTED`
  - RED: empty result
- **Cadence**: per run
- **Sample**: `{"id":11,"name":"champion_status_dist","value":{"STAGING":12,"REJECTED":34,"DEPLOYABLE":4,"LIVE":2},"status":"GREEN"}`

### 12. A13 feedback status (cron health)

- **Source**: `tail -200 /tmp/zangetsu_arena13_feedback.log` → last `MODE=` and last successful run timestamp
- **Threshold**:
  - GREEN: last success ≤ 10 min ago
  - YELLOW: last success ≤ 30 min ago
  - RED: last success > 30 min ago
- **Cadence**: per run
- **Sample**: `{"id":12,"name":"a13_feedback","value":{"mode":"FEEDBACK","last_ok":"2026-04-27T07:55:01Z","age_s":120},"status":"GREEN"}`

### 13. A23 intake count (last 1h)

- **Source**: `grep -c "INTAKE_OK" /tmp/zangetsu_arena23.log` filtered by 1h window; or DB `SELECT count(*) FROM arena23_intake WHERE ts > now() - interval '1 hour'`
- **Threshold**:
  - GREEN: `count >= 1`
  - YELLOW: `count == 0` AND staging_rows == 0 (consistent empty pipeline)
  - RED: `count == 0` AND staging_rows > 0 (intake stalled while supply exists)
- **Cadence**: per run
- **Sample**: `{"id":13,"name":"a23_intake","value":{"h1":0},"status":"YELLOW","note":"empty pipeline — consistent with current runtime state"}`

### 14. A45 downstream status

- **Source**: `tail -200 /tmp/zangetsu_arena45.log` → last heartbeat or `IDLE` marker; cross-check process pid present
- **Threshold**:
  - GREEN: heartbeat within 10 min OR explicit `IDLE` marker AND pid alive
  - YELLOW: no heartbeat 10–30 min, pid alive
  - RED: pid not alive
- **Cadence**: per run
- **Sample**: `{"id":14,"name":"a45_downstream","value":{"state":"IDLE","pid_alive":true,"last_hb_age_s":312},"status":"GREEN"}`

### 15. `arena_batch_metrics` availability (last 5 min)

- **Source**: `SELECT count(*) FROM arena_batch_metrics WHERE event_ts > now() - interval '5 minutes'`
- **Threshold**:
  - GREEN: `count >= 1`
  - YELLOW: `count == 0` AND last event ≤ 30 min ago
  - RED: `count == 0` AND last event > 30 min ago (or table missing)
- **Cadence**: per run
- **Sample**: `{"id":15,"name":"arena_batch_metrics_5m","value":{"count":3,"last_event_age_s":47},"status":"GREEN"}`

### 16. `UNKNOWN_REJECT` ratio

- **Source**: `grep -c "UNKNOWN_REJECT" /tmp/zangetsu_a1_w*.log` over last 1h, divided by total rejections
- **Threshold**:
  - GREEN: `ratio == 0`
  - YELLOW: `0 < ratio <= 0.01`
  - RED: `ratio > 0.01`
- **Cadence**: per run
- **Note**: Any RED here ⇒ engine_jsonl reason taxonomy needs extension.
- **Sample**: `{"id":16,"name":"unknown_reject_ratio","value":0.0,"status":"GREEN"}`

### 17. `deployable_count` (Constitution §17.1)

- **Source**: `SELECT deployable_count FROM zangetsu_status` (the Constitution-mandated VIEW)
- **Threshold**:
  - GREEN: `count >= 1`
  - YELLOW: `count == 0` AND `last_live_at_age_h <= 6`
  - RED: `count == 0` AND `last_live_at_age_h > 6` (Calcifer block trigger)
- **Cadence**: per run
- **Sample**: `{"id":17,"name":"deployable_count","value":4,"status":"GREEN"}`

### 18. Cold-start dry-run result count (last 24h) — **BLOCKED (Phase 4 schema gap)**

- **Source**: `SELECT count(*) FROM cold_start_dryrun_results WHERE ts > now() - interval '24 hours'` (table missing in Phase 4)
- **Status**: `BLOCKED` pending schema migration
- **Note**: Once schema lands, GREEN if ≥1 successful dry-run in 24h, RED if 0.

### 19. Data freshness (oldest stale symbol timestamp)

- **Source**: `SELECT symbol, max(bar_ts) FROM market_data_1m GROUP BY 1 HAVING max(bar_ts) < now() - interval '5 minutes' ORDER BY 2 LIMIT 1`
- **Threshold**:
  - GREEN: no symbol staler than 5 min
  - YELLOW: ≥1 symbol stale 5–15 min
  - RED: ≥1 symbol stale > 15 min
- **Cadence**: per run
- **Sample**: `{"id":19,"name":"data_freshness","value":{"oldest":{"symbol":"ETHUSDT","stale_s":42}},"status":"GREEN"}`

### 20. DB schema health (v0.7.1 objects present?)

- **Source**: compare `pg_class` snapshot against expected manifest `docs/recovery/manifest_v0_7_x.sha256`
- **Threshold**:
  - GREEN: snapshot hash matches manifest
  - YELLOW: snapshot is superset (extra objects, none missing)
  - RED: any expected object missing
- **Cadence**: per run
- **Note**: This is the gate that, today, marks 8 of 22 metrics BLOCKED.
- **Sample**: `{"id":20,"name":"schema_health","value":{"missing":["champion_pipeline_fresh","cold_start_dryrun_results"]},"status":"RED"}`

### 21. Gate-A / Gate-B last status on `origin/main`

- **Source**: `gh run list --branch main --workflow gate-a --limit 1 --json conclusion,headSha,url,createdAt` (and same for `gate-b`)
- **Threshold**:
  - GREEN: both `conclusion == success` on current `origin/main` HEAD
  - YELLOW: success on prior HEAD (no run yet for current HEAD)
  - RED: any `conclusion in {failure, cancelled, timed_out}` on current HEAD
- **Cadence**: per run
- **Sample**: `{"id":21,"name":"gate_a_b","value":{"a":{"conclusion":"success","head":"9f6dc60"},"b":{"conclusion":"success","head":"9f6dc60"}},"status":"GREEN"}`

### 22. Controlled-diff status

- **Source**: `scripts/controlled_diff.sh --json` (latest run output, or fresh exec)
- **Threshold**:
  - GREEN: `forbidden_count == 0`
  - YELLOW: never (binary)
  - RED: `forbidden_count >= 1`
- **Cadence**: per run
- **Sample**: `{"id":22,"name":"controlled_diff","value":{"forbidden_count":0},"status":"GREEN"}`

---

## BLOCKED-by-Phase-4 Summary

The Phase 4 DB schema gap (missing `champion_pipeline_fresh`, missing
`cold_start_dryrun_results`, partial `arena_batch_metrics`) blocks the
following metrics today:

- 9 (fresh_rows)
- 18 (cold_start_dryrun_24h)

It also degrades — but does not fully block — these metrics, which depend on
`champion_pipeline_staging` populating downstream tables:

- 4, 5, 6 (train/val/sharpe distributions emit but with lower row counts)
- 7 (cross-symbol consistency)
- 11 (champion_pipeline status distribution — currently no DEPLOYABLE)
- 17 (deployable_count — currently 0)

Counting fully blocked + materially degraded = **8 of 22 metrics blocked or
degraded by Phase 4 schema gap.** When the Phase 4 migration lands and the
manifest-comparison in metric 20 returns GREEN, all 22 should report normally.

---

## Performance and Sampling

- Default cadence: every 5 minutes (cron `*/5 * * * *`).
- Per-run wall-clock budget: ≤ 3 seconds. Each DB query is independently timed
  and given an internal 500 ms timeout; on timeout the metric reports
  `BLOCKED` with `note: "query timeout"` and the run still completes.
- Idempotent: running back-to-back yields identical structure (timestamps differ).
- No writes. CLI is read-only; no DB or filesystem mutation.

---

## Files Cited (for Implementation Phase, not this Order)

- `/tmp/zangetsu_a1_w*.log` — A1 worker logs (4 workers)
- `/tmp/zangetsu_arena13_feedback.log` — A13 feedback cron
- `/tmp/zangetsu_arena23.log` — A23 intake
- `/tmp/zangetsu_arena45.log` — A45 downstream
- `/home/j13/j13-ops/engine.jsonl` — engine event stream
- `docs/recovery/manifest_v0_7_x.sha256` — schema-health expected hash
- `scripts/controlled_diff.sh` — controlled-diff source

DB queries target `deploy-postgres-1` Docker container (`j13ops` DB).

---

## Out of Scope for Order 4-2

- Implementation (no code; this is a specification).
- Prometheus textfile emitter detail (sketched via `--emit-prom` flag only).
- Dashboard rendering (downstream of `dashboard_status_logic.json`).
- Alerting routing (Telegram thread routing handled by existing infrastructure).
