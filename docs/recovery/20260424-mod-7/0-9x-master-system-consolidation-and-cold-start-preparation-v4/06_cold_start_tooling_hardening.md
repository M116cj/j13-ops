# 06 — Cold-Start Tooling Hardening (Track E)

## 1. Target

`zangetsu/scripts/alpha_zoo_injection.py` — the only cold-start tool with potential for live DB writes.

## 2. Pre-PR State

- Default mode: would proceed to `css.run_for_strategy(...)` which opens DB connection and writes to `champion_pipeline_staging`
- `--dry-run-one` flag was parsed but UNIMPLEMENTED (body never read it)
- No precondition check for DB schema or validator function existence
- A user running the script with no arguments would attempt LIVE writes

This is the **default-unsafe** state called out in PR #41 as B3 (HIGH-severity blocker).

## 3. Post-PR State (this PR adds)

### 3.1 Argparse flags (new)

| Flag | Default | Purpose |
| --- | --- | --- |
| `--inspect-only` | OFF | List formula table; NO compile, NO backtest, NO DB write |
| `--dry-run` | OFF | Compile + simulate validation; write JSONL plan to `/tmp/sparse_candidate_dry_run_plans.jsonl`; ZERO DB writes |
| `--no-db-write` | **ON (default)** | Hard-block any DB write attempt |
| `--confirm-write` | OFF (default deny) | Required for actual DB write; also requires DB schema check |

### 3.2 Run-time dispatch logic (in `run()`)

```python
# 1. Print safety contract banner first (always)
log.info("=== Safety contract ===")
log.info("  inspect_only   : ...")
# ... formula count + source tags + write target + validator dep displayed

# 2. INSPECT-ONLY: print + exit. NO compile, NO backtest, NO DB.
if getattr(args, "inspect_only", False):
    [print formula inventory]
    return

# 3. DRY-RUN: write JSONL plan to /tmp/. ZERO DB writes (no asyncpg.connect).
if getattr(args, "dry_run", False):
    [write plan_row dict per formula to /tmp/sparse_candidate_dry_run_plans.jsonl]
    return

# 4. NO-DB-WRITE: explicit block (default ON ensures user must override)
if getattr(args, "no_db_write", True) and not getattr(args, "confirm_write", False):
    sys.exit(2)

# 5. DEFAULT-DENY: require --confirm-write
if not getattr(args, "confirm_write", False):
    log.error("ABORT: --confirm-write was NOT set. ...")
    sys.exit(2)

# 6. PRECONDITION CHECK (only reached if --confirm-write set)
db = await asyncpg.connect(...)
for required in ("champion_pipeline_staging", "champion_pipeline_fresh"):
    if not exists in pg_class:
        log.error("ABORT: required DB object missing: %s")
        sys.exit(3)
if not admission_validator function exists:
    log.error("ABORT: admission_validator() function missing")
    sys.exit(4)

# 7. LEGACY PATH (only if all 6 checks above pass)
[original css.run_for_strategy logic]
```

### 3.3 Default-Deny Verification

Running `python alpha_zoo_injection.py` with NO arguments:
1. Banner prints (safety contract)
2. `inspect_only` is False → not inspect-only branch
3. `dry_run` is False → not dry-run branch
4. `no_db_write` is True (default) AND `confirm_write` is False → ABORT with exit 2

→ **By default, the tool refuses to do anything destructive.** User must explicitly choose `--inspect-only`, `--dry-run`, or `--confirm-write`.

### 3.4 Defense-in-Depth Layering

| Layer | Effect |
| --- | --- |
| Inspect-only | terminates before any compile/backtest/connect |
| Dry-run | terminates before any DB connect; writes plan to /tmp only |
| No-db-write (default ON) | blocks even if user accidentally tries to write |
| Confirm-write | required gate to reach DB code path |
| Precondition check | blocks DB write if schema/validator missing (defense against Track A BLOCKED state) |
| `admission_validator()` | DB-side gate (when present) — staging → fresh promotion |
| `fresh_insert_guard` trigger | DB-side gate against direct fresh INSERT |

→ **5 layers of defense in code + 2 layers in DB.** Direct fresh write is impossible.

## 4. Deprecated Path Verification

| Script | Guard Status |
| --- | --- |
| `seed_101_alphas.py` | `# DEPRECATED in v0.7.1 (2026-04-20 governance)` + `print("REFUSED: this module is DEPRECATED")` + early exit |
| `seed_101_alphas_batch2.py` | same pattern |
| `factor_zoo.py` | same pattern |
| `alpha_discovery.py` | same pattern (despite running every */30 cron — the guard prints REFUSED and exits, so cron firing is harmless) |

## 5. Test Coverage

- Existing tests (in `zangetsu/tests/`) cover the legacy path (which is now post-confirm-write).
- New `--inspect-only` path: tested via manual run (banner + formula list + return)
- New `--dry-run` path: tested via manual run (writes JSONL plan to /tmp; zero DB connect)
- `--no-db-write` precondition: tested via running without `--confirm-write` (exits 2)
- `--confirm-write` precondition: tested via running with `--confirm-write` against current Track-A-BLOCKED DB (exits 3 — required schema missing)

## 6. Gemini Track T F1 Resolution

Original review found `--dry-run` and `--no-db-write` were dead code (defined in argparse but never read). This PR's run() implementation fixes that — both flags now have real run-time effect, not just argparse stubs.

## 7. Track E Verdict

→ **GREEN.** Tool is safe by default. Direct fresh write is impossible. Default-deny enforced. Validation contract dependency surfaced via DB precondition check. Deprecated paths confirmed blocked.

## 8. Forbidden Operations Honored

- NO live DB writes performed during this PR
- NO deprecated seed execution
- NO bypass of validation contract
- All changes are ADDITIVE safety hardening
