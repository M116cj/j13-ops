# Zangetsu V3.1 Security Audit — 2026-04-06

## Summary: YELLOW

No RED blockers for paper trading. Two items escalate to RED for real-money trading.

## Findings

### risk_manager.py — GREEN
- position_frac hard-clamped via max_net_exposure=0.25. PASS.
- Cards cannot override RiskLimits. PASS.
- Every trade goes through check_new_position(). PASS.

### stale_breaker.py — YELLOW
- Uses time.monotonic() — immune to clock drift. PASS.
- **ISSUE**: No recovery debounce. Single bar after disconnect resumes trading immediately. No 3-consecutive-bar requirement. Severity: MEDIUM.

### journal.py — GREEN
- Append-only with atomic writes (temp + os.replace()). PASS.
- No file locking (acceptable for single-threaded). Severity: LOW.

### main_loop.py — YELLOW
- **ISSUE 1**: position_overlay is DEAD CODE — never called. 4-layer sizing not implemented. MEDIUM.
- **ISSUE 2**: position_frac not clamped at load. Tampered card could set any value. MEDIUM.

### cards/exporter.py — YELLOW
- **ISSUE**: Checksum write-only, never verified on load. Tampered cards accepted silently. MEDIUM.

### Crash Recovery — YELLOW
- **ISSUE**: No position state persistence. After crash, no knowledge of open positions. MEDIUM (paper), RED (live).

### DB Disconnect — YELLOW
- on_new_bar() does zero I/O — DB outage no effect during trading. PASS.
- DataLoader startup crashes on DB unavailability. LOW-MEDIUM.

## Priority

| Priority | Finding | Severity |
|----------|---------|----------|
| Fix before paper | position_overlay dead code | MEDIUM |
| Fix before paper | position_frac not clamped at load | MEDIUM |
| Fix before live | Checksum never verified on load | MEDIUM |
| Fix before live | No position state persistence | MEDIUM |
| Fix before live | No stale recovery debounce | MEDIUM |
