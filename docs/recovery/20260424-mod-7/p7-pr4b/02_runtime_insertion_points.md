# P7-PR4B — Runtime Insertion Points

All runtime changes are additive, exception-safe, non-blocking, and
behavior-invariant. The single modified runtime file is
`zangetsu/services/arena23_orchestrator.py`, authorized under the
0-9M `EXPLAINED_TRACE_ONLY` controlled-diff pathway.

## 1. Module-level imports + helpers

**File**: `zangetsu/services/arena23_orchestrator.py`
**Lines**: ~150-330 (new block, immediately after the `Rust engine`
try-import and before the `WORKER_ID = "arena23"` constant)

Added:

- `try: from zangetsu.services.arena_pass_rate_telemetry import …`
  with `_P7PR4B_TELEMETRY_AVAILABLE` flag.
- `try: from zangetsu.services.arena_rejection_taxonomy import classify`
  with `_P7PR4B_REJECTION_TAXONOMY_AVAILABLE` flag.
- `try: from zangetsu.services.generation_profile_identity import
  safe_resolve_profile_identity` with
  `_P7PR4B_PROFILE_IDENTITY_AVAILABLE` flag.
- `_P7PR4B_BATCH_FLUSH_SIZE` (env-tunable, default 20) — telemetry
  batch flush threshold. Bounded `>=1` defensively.
- `_p7pr4b_resolve_passport_profile(passport)` — best-effort profile
  identity extraction from upstream A1 / passport metadata.
  UNKNOWN / UNAVAILABLE fallbacks. Never raises.
- `_p7pr4b_make_acc_safe(stage, …)` — exception-safe
  `ArenaStageMetrics` construction.
- `_p7pr4b_canonicalize_reason(raw_reason, stage)` — taxonomy classify
  wrapper. Falls back to `"UNKNOWN_REJECT"` on any failure.
- `_p7pr4b_record_outcome(passport, *, stage, outcome, reject_reason,
  acc, batch_seq, in_batch, run_id, consumer_profile, flush_size, log,
  safe_emit)` — generic per-champion accumulator update + flush.
- `_p7pr4b_a2_record(passport, **kwargs)` /
  `_p7pr4b_a3_record(passport, **kwargs)` — stage-bound shortcuts.
- `_P7PR4BLogCapture` — passive logger wrapper that observes A2 / A3
  reject log lines so canonical reasons can be classified after each
  champion is processed. Forwards every method to the wrapped logger.

## 2. main() — accumulator state initialisation

**File**: `zangetsu/services/arena23_orchestrator.py`
**Lines**: inside `async def main()`, immediately before
`running = True`.

Added (all variables prefixed with `_p7pr4b_` for unambiguous origin):

- `_p7pr4b_run_id` — `f"a23-{int(time.time())}-{os.getpid()}"`.
- `_p7pr4b_consumer_profile` — orchestrator-level profile derived from
  `_V10_ENTRY_THR` / `_V10_EXIT_THR` / `_V10_MIN_HOLD` / `_V10_COOLDOWN`.
- `_p7pr4b_a2_acc`, `_p7pr4b_a3_acc` — `ArenaStageMetrics` accumulators.
- `_p7pr4b_a2_batch_seq`, `_p7pr4b_a3_batch_seq` — monotonically
  increasing batch sequence numbers for `batch_id` generation.
- `_p7pr4b_a2_in_batch`, `_p7pr4b_a3_in_batch` — counts since last flush.
- `_p7pr4b_log` — `_P7PR4BLogCapture(log)` shared by A2 / A3 process
  calls so canonical reject reasons can be observed.

## 3. A3 emission call site

**File**: `zangetsu/services/arena23_orchestrator.py`
**Location**: inside `if champion:` block of A3 path, right after the
A3 try / except / log_transition block, before the elapsed timer.

```python
# ── P7-PR4B: telemetry update for A3 ──────────────────
try:
    if _P7PR4B_TELEMETRY_AVAILABLE:
        _passport_a3 = (
            json.loads(_p7pr4b_a3_passport_raw)
            if isinstance(_p7pr4b_a3_passport_raw, str)
            else _p7pr4b_a3_passport_raw
        )
        _raw_a3 = (
            None
            if _p7pr4b_a3_outcome != "REJECTED"
            else (_p7pr4b_log.consume_a3() or "no_valid_atr_tp")
        )
        _p7pr4b_a3_acc, _p7pr4b_a3_batch_seq, _p7pr4b_a3_in_batch = (
            _p7pr4b_a3_record(
                _passport_a3,
                outcome=_p7pr4b_a3_outcome,
                reject_reason=_raw_a3,
                acc=_p7pr4b_a3_acc,
                batch_seq=_p7pr4b_a3_batch_seq,
                in_batch=_p7pr4b_a3_in_batch,
                run_id=_p7pr4b_run_id,
                consumer_profile=_p7pr4b_consumer_profile,
                flush_size=_P7PR4B_BATCH_FLUSH_SIZE,
                log=log,
            )
        )
except Exception:
    pass  # never propagate
```

The captured outcome (`PASSED` / `REJECTED` / `ERROR`) is set by the
existing A3 result branches; `_p7pr4b_a3_passport_raw` is read from the
champion dict at the top of the block.

## 4. A2 emission call site

**File**: `zangetsu/services/arena23_orchestrator.py`
**Location**: inside `if champion:` block of A2 path. Two emission
points:

1. **Dedup-skip path** — inline accumulator update before the existing
   `continue` so the dedup-rejected champion is recorded with the
   canonical `duplicate_indicator_combo` reason. The original `continue`
   semantics are preserved exactly.
2. **Normal A2 path** — analogous to A3, after the try / except /
   log_transition block.

`_p7pr4b_log.consume_a2()` retrieves the most-recent A2 reject log line
emitted by `process_arena2`.

## 5. Logger wrap

`process_arena2` and `process_arena3` are now invoked with
`_p7pr4b_log` (the `_P7PR4BLogCapture` wrapper) instead of `log`. The
wrapper forwards every method (`info` / `warning` / `error` / `debug` /
…) to the underlying `StructuredLogger`; only `info()` is intercepted
for the side-effect of caching the latest A2 / A3 reject log line. This
introduces zero behavioral change to log emission.

## 6. Shutdown flush

**File**: `zangetsu/services/arena23_orchestrator.py`
**Location**: end of `main()`, immediately after the PGQueuer close
block and before `await db.close()`.

```python
# ── P7-PR4B: flush any remaining A2 / A3 batch accumulators ────
try:
    if _P7PR4B_TELEMETRY_AVAILABLE and _p7pr4b_a2_acc is not None:
        _p7pr4b_safe_emit_a2(_p7pr4b_a2_acc, deployable_count=None, log=log)
        _p7pr4b_a2_acc = None
except Exception:
    pass
try:
    if _P7PR4B_TELEMETRY_AVAILABLE and _p7pr4b_a3_acc is not None:
        _p7pr4b_safe_emit_a3(_p7pr4b_a3_acc, deployable_count=None, log=log)
        _p7pr4b_a3_acc = None
except Exception:
    pass
```

## 7. A4 / A5 orchestrator (`arena45_orchestrator.py`)

**Not modified by P7-PR4B.** Order §11.3 mentions A3 wiring "or actual
A3 orchestrator equivalent" — the actual A3 evaluation lives inside
`arena23_orchestrator.process_arena3` (despite the file name suggesting
otherwise). `arena45_orchestrator.py` runs A4 (CANDIDATE/DEPLOYABLE
gate) and A5 (ELO tournament), neither of which is in P7-PR4B scope.

## 8. Files NOT modified

- `zangetsu/services/arena_pipeline.py` — A1 emission unchanged.
- `zangetsu/services/arena_gates.py` — pass/fail logic unchanged.
- `zangetsu/services/arena_rejection_taxonomy.py` — canonical
  vocabulary unchanged.
- `zangetsu/config/settings.py` — thresholds unchanged.
- All `zangetsu/engine/` modules — alpha generation / formula DSL /
  signal generation unchanged.
- `zangetsu/services/arena45_orchestrator.py` — A4 / A5 unchanged.

## 9. Controlled-diff classification

Expected:

- `config.arena23_orchestrator_sha` changes → **EXPLAINED_TRACE_ONLY**
  via `--authorize-trace-only config.arena23_orchestrator_sha`.
- All other CODE_FROZEN SHAs zero-diff.
- `repo.git_status_porcelain_lines` changes → EXPLAINED.
- 0 FORBIDDEN.
