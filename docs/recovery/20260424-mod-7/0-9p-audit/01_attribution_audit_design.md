# 01 — Attribution Audit Design

## 1. Purpose

Validate that 0-9P passport persistence actually delivers clean profile
attribution before PR-C / 0-9R-IMPL-DRY consumes it. Offline / read-only.

## 2. Scope

New offline tool: `zangetsu/tools/profile_attribution_audit.py`.

Imports only:
- `zangetsu.services.generation_profile_identity` (constants +
  `resolve_attribution_chain` helper, no runtime side effects).

Does **not** import:
- `arena_pipeline` / `arena23_orchestrator` / `arena45_orchestrator`
- `alpha_engine` / `alpha_signal_live` / `live/`
- `feedback_budget_allocator` (already dry-run only — but kept
  separate for layering)

## 3. Public surface

```
AttributionAuditResult       — dataclass, 24 required fields
audit(events)                 — main entry; returns AttributionAuditResult
safe_audit(events)            — exception-safe wrapper (RED on failure)
classify_attribution_source   — coarse passport / orchestrator / unknown
classify_verdict              — pure threshold logic, returns (verdict, reasons)
verdict_blocks_consumer_phase — True only on RED
ReplayValidationResult        — dataclass for replay tallies
replay_validate(passports)    — runs resolve_attribution_chain over passports
parse_event_log_lines         — best-effort JSON-line parser
required_audit_fields         — schema lock for tests
```

No `apply` / `commit` / `execute` symbols.

## 4. Output schema

`AttributionAuditResult` 24 fields (see `02_replay_validation_contract.md`
§3 for the full table).

## 5. Verdict thresholds (per TEAM ORDER §5)

| Rate | GREEN max | YELLOW max | RED |
| --- | --- | --- | --- |
| `unknown_profile_rate` | 0.05 | 0.20 | > 0.20 |
| `profile_mismatch_rate` | 0.01 | 0.05 | > 0.05 |
| `fingerprint_unavailable_rate` | 0.05 | 0.20 | > 0.20 |

Worst-of-three drives the overall verdict.

`verdict_blocks_consumer_phase(VERDICT_RED) is True` — PR-C may not
proceed when verdict is RED.

## 6. Read-only guarantees

- Input never mutated (verified by JSON snapshot test).
- Tool not imported by any runtime module (verified by source-text
  test that walks `services/*.py`).
- All exceptions caught; tool never propagates failure to callers.
