# 42-16 Performance Profiling Plan — ZANGETSU Master Consolidation 4-2 / Track Q

**Status:** Design only — DO NOT optimize as part of this track
**Owner:** Track Q (Profiling)
**Audience:** Lead, future Track R (Optimization) once approved
**Scope:** A1 generation pipeline, validation/backtest, indicator cache, DB I/O, multiprocessing/async, telemetry
**Constitution refs:** §17.1 VIEW-based status (profile must not break it), §17.6 stale-service rule (profilers must not freeze workers past mtime contract)

> **Forbidden:** any code change that alters behavior. This document plans measurement only. The deliverable of Track Q is *numbers + bottleneck hypotheses*, not faster code.

---

## 0. Ground rules

- **Read-only profilers** (py-spy, cProfile via `-X importtime`/`runpy`, OS counters) preferred over instrumentation that mutates source.
- Wall-clock measurements via `time.perf_counter()` are acceptable IF wrapped in a feature flag toggled off by default.
- All profiler runs land in `docs/profiling/YYYYMMDD-<target>.md` plus raw artifacts in `~/profiling-artifacts/` on Alaya (not in repo).
- Sampling profilers must not exceed 5 % CPU overhead during canary windows.
- Every profiling session **must** terminate before its source mtime contract expires (§17.6); if a session needs > 1 h, take a snapshot and exit.

---

## 1. Targets — 14 measurement objectives

### Target 1 — A1 generation CPU per round
- **Current observation:** ~10 candidates accepted/round, 18.7k rejected/round, multiple rounds/min.
- **Method:** `py-spy record --pid <A1_PID> --duration 300 --output a1_w<N>.svg --rate 50`
- **Threshold:** > 80 % single-core utilization sustained for > 10 min on a single A1 worker = "too-slow" signal.
- **Cadence:** once per canary window (each release), plus on-demand when reject mix drifts.
- **Tools:** py-spy (already installed on Alaya — verify with `which py-spy`).
- **Expected bottleneck:** DEAP genetic operators + per-candidate validation gate chain.

### Target 2 — Validation/backtest runtime per candidate
- **Current observation:** PR #40 measured 663 evals in 29.6 s = 22 evals/s.
- **Method:** `time.perf_counter()` wrapping `validate_candidate()`; aggregate to per-stage histogram (cost, position, slippage, gate set).
- **Threshold:** p95 per-candidate > 100 ms sustained = "too-slow".
- **Cadence:** every offline replay run.
- **Tools:** stdlib only.
- **Expected bottleneck:** indicator recomputation per candidate when cache misses.

### Target 3 — Formula compilation time (DEAP `ast_to_callable`)
- **Method:** cProfile a representative 1k-formula compilation batch: `python -m cProfile -o ast.prof bench/compile_1k.py`
- **Threshold:** > 1 ms median per formula = candidate for AST-cache reuse.
- **Cadence:** once per release; once on schema change to indicator namespace.
- **Tools:** stdlib cProfile + `snakeviz` for inspection.
- **Expected bottleneck:** repeated AST traversal for shared subtrees.

### Target 4 — Indicator cache hit/miss
- **Current observation:** 126 indicator terminals × per-symbol cache.
- **Method:** add (read-only via existing telemetry) `cache_get/cache_put` counters; log `(hits, misses, evictions)` per round to engine.jsonl.
- **Threshold:** hit rate < 70 % sustained = under-sized cache or wrong key.
- **Cadence:** per round (already covered if telemetry already emits — verify).
- **Tools:** existing telemetry — no new dep.
- **Expected bottleneck:** working set > LRU capacity for novel symbol enumeration.

### Target 5 — Offline replay throughput
- **Current observation:** 22 evals/s single-thread (PR #40 baseline).
- **Method:** `python -m timeit -n 1 -r 3 'offline_replay.run(N=663)'`
- **Threshold:** drop > 20 % vs PR #40 baseline = regression.
- **Cadence:** every PR touching engine/, offline_replay/, indicator_engine/, validation gates.
- **Tools:** stdlib timeit + jsonl diff vs baseline.
- **Expected bottleneck:** same as Target 2.

### Target 6 — Calibration matrix runtime
- **Current observation:** 405-cell matrix in 29.6 s on 1 thread (PR #40).
- **Method:** `time.perf_counter()` around `calibration_matrix.build()`; record per-cell time histogram.
- **Threshold:** > 100 ms/cell median = slow.
- **Cadence:** per calibration run.
- **Tools:** stdlib.
- **Expected bottleneck:** per-cell shared backtest setup not amortized.

### Target 7 — DB query latency
- **Current observation:** no DB writes due to schema gap; once v0.7.1 migration applied → staging insert + admission_validator path active.
- **Method:** `EXPLAIN (ANALYZE, BUFFERS) <query>` for the 5 hot statements; `pg_stat_statements` snapshot diff over 1 h windows.
- **Threshold:** any query mean > 50 ms or p95 > 250 ms = candidate.
- **Cadence:** post-migration baseline + every PR touching `*.sql` or asyncpg statements.
- **Tools:** psql + `pg_stat_statements` (verify extension present: `\dx`).
- **Expected bottleneck:** missing index on `champion_pipeline_fresh(state, created_at)` or admission_validator JOIN.

### Target 8 — JSONL parsing
- **Current observation:** engine.jsonl + per-worker `/tmp/zangetsu_a1_w*.log` ~11+ MB each.
- **Method:** `time python -c "import json; [json.loads(l) for l in open('engine.jsonl')]"` baseline; compare vs `orjson` (do **not** swap — measure only).
- **Threshold:** parse > 5 s on 11 MB file = slow.
- **Cadence:** weekly during canary, plus pre/post any log-format change.
- **Tools:** stdlib + orjson installed in throwaway venv.
- **Expected bottleneck:** stdlib json on dict-heavy lines.

### Target 9 — Multiprocessing overhead
- **Current observation:** 4 A1 workers + GP loop within each.
- **Method:** measure spawn time (`time.perf_counter()` around `multiprocessing.Process.start()`) and IPC throughput on the result queue (`q.qsize()` sampled at 1 Hz).
- **Threshold:** spawn > 2 s (cold) is fine; > 500 ms IPC round-trip on small payload = slow.
- **Cadence:** once per release; on-demand when worker count changes.
- **Tools:** stdlib.
- **Expected bottleneck:** pickle overhead on indicator descriptors + queue contention.

### Target 10 — Async overhead (asyncpg)
- **Method:** `asyncio.get_event_loop().slow_callback_duration = 0.05`; count slow-callback warnings in logs over 1 h.
- **Threshold:** > 5 slow-callback warnings/h = blocking inside coroutine.
- **Cadence:** continuous via existing log channel; weekly aggregate.
- **Tools:** stdlib asyncio.
- **Expected bottleneck:** synchronous `json.dumps` or filesystem write inside `async def`.

### Target 11 — Memory footprint (per-worker RSS)
- **Method:** `ps -o pid,rss,cmd -p <PIDS>` sampled every 60 s for 6 h; chart RSS over time per worker; supplement with `tracemalloc` snapshot at start vs +30 min for top 20 allocators.
- **Threshold:** RSS growth > 100 MB/h sustained = leak.
- **Cadence:** continuous OS sampler; tracemalloc once per release.
- **Tools:** OS `ps` + stdlib tracemalloc.
- **Expected bottleneck:** indicator cache without bounded eviction; DEAP population history growth.

### Target 12 — Disk I/O
- **Method:** `iostat -x 5` during canary window for 30 min; per-process via `iotop -b -n 60 -d 5` filtered to worker PIDs.
- **Threshold:** sustained write > 10 MB/s/worker = excessive logging or jsonl bloat.
- **Cadence:** weekly canary.
- **Tools:** sysstat (iostat) + iotop (verify installed: `which iostat iotop`).
- **Expected bottleneck:** `_emit_a1_lifecycle_safe` writing every event to engine.jsonl.

### Target 13 — Log volume (per-hour, per-day)
- **Method:** `find /tmp/zangetsu_a1_w*.log /home/j13/j13-ops/zangetsu/logs/ -newer <ts> -exec wc -l {} \;` summed over 1 h; daily rollup via cron-friendly `du -sb`.
- **Threshold:** > 100 MB/day total or > 1 M lines/day = unsustainable; re-evaluate event filter.
- **Cadence:** daily rollup logged to `docs/profiling/`.
- **Tools:** stdlib + `du`/`wc`.
- **Expected bottleneck:** lifecycle events fired per rejected candidate (18.7k/round × multiple rounds/min).

### Target 14 — Telemetry emission cost
- **Method:** `time.perf_counter()` around `_emit_a1_lifecycle_safe` for one round; compare emission-on vs emission-off (feature flag) measured wall-clock.
- **Threshold:** emission overhead > 5 % of round CPU = candidate.
- **Cadence:** once per release; on-demand when telemetry schema changes.
- **Tools:** stdlib + existing feature flag.
- **Expected bottleneck:** synchronous JSON serialization per event.

---

## 2. Cross-cutting design rules

- **No prod-impact** — all profilers must run on a worker that is canary-tagged or in shadow. Never attach `py-spy --native` to a worker handling live order flow.
- **Reproducibility** — every profiling artifact tagged with `(commit_sha, alaya_image_id, dataset_window, started_at, ended_at)`. Without these the artifact is not citable.
- **Bottleneck hypothesis is mandatory** — every profiling run produces (1) raw artifact, (2) `docs/profiling/YYYYMMDD-<target>.md` with hypothesis + supporting evidence + recommended next action (which must be "design Track R proposal", not "patch now").
- **No optimization** — Q1 dimension "scope creep" applies aggressively here. If a measurement reveals a 2-line obvious fix, write it as a Track R proposal, do not commit.
- **Drift detection** — each target has a baseline value (most have one already from PR #40). Track R triggers only on > 20 % regression OR threshold breach.

---

## 3. Quality gates for this plan itself

| Gate | Definition for Track Q                                                                          |
|------|--------------------------------------------------------------------------------------------------|
| Q1   | Profilers do not crash workers, do not break stale-service contract, do not leak secrets to logs |
| Q2   | Each target has a documented recovery path if its profiler hangs (kill PID + verify worker)     |
| Q3   | No optimization, no premature instrumentation; exactly the 14 targets, no more, no less          |

---

## 4. Out-of-scope (explicit non-goals)

- Distributed tracing (Jaeger / OpenTelemetry collector) — design later if Targets 9 + 10 surface coupling.
- GPU profiling — A1/A23/A45 are CPU-bound; defer.
- Network profiling beyond asyncpg — exchange-side latency is its own track.
- Database vacuum / autovacuum tuning — surfaces from Target 7 if needed; out of scope here.

---

## 5. Deliverables of Track Q (when executed, not now)

1. `docs/profiling/YYYYMMDD-baseline.md` — single rollup of all 14 targets, current numbers.
2. `~/profiling-artifacts/` on Alaya — raw `*.svg`, `*.prof`, `*.jsonl` files (not in git; size budget 1 GB).
3. Telegram SUCCESS message with summary table.
4. `docs/decisions/YYYYMMDD-track-Q-baseline.md` referenced by zangetsu_status VIEW (`profiling_baseline_at` column candidate — **propose only**, do not add yet).
5. List of Track R proposals (each its own /team or /build session, gated separately).

---

## 6. Risk register

| Risk                                        | Mitigation                                                       |
|---------------------------------------------|------------------------------------------------------------------|
| py-spy attach causes worker SIGSTOP/SIGCONT | use `--rate 50` (low overhead), never on live-order worker       |
| cProfile output > 200 MB                    | scope to one round at a time, store under `~/profiling-artifacts/` not /tmp |
| tracemalloc keeps refs to objects, masks leak | use `start()/take_snapshot()/stop()` discipline; never leave running |
| iotop / sysstat not installed on Alaya      | document gap; install via /calcifer if approved                  |
| Profiler artifact accidentally committed    | `.gitignore` already excludes `*.svg`, `*.prof`; verify before each session |

---

## 7. Pre-execution checklist (when Track Q is greenlit)

- [ ] `which py-spy iostat iotop` all present on Alaya
- [ ] `pg_stat_statements` extension active in `zangetsu_v5`
- [ ] `~/profiling-artifacts/` exists, writable by `j13`
- [ ] No live-order worker selected as target
- [ ] §17.6 stale-service check baseline captured before profiling starts
- [ ] Telegram thread 356 notified: profiling window + duration + worker scope

---
*End of Track Q plan. 14 targets, 0 optimizations.*
