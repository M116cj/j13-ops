# 09 — Cold-Start Tooling Parameter Audit

## 1. Inventory

| Tool path | Purpose | Default mode | Write target | Dry-run | Deprecated |
| --- | --- | --- | --- | --- | --- |
| `zangetsu/scripts/alpha_zoo_injection.py` | inject 30 hand-translated formulas into staging | inject (no dry-run) | `champion_pipeline_staging` (does not exist) | `--dry-run-one` flag PARSED but UNIMPLEMENTED | NO but BLOCKED |
| `zangetsu/services/seed_101_alphas.py` | seed 101 WorldQuant formulas | per VERSION_LOG: marked DEPRECATED guard | n/a | n/a | **DEPRECATED** |
| `zangetsu/services/seed_101_alphas_batch2.py` | batch 2 of 101 formulas | per VERSION_LOG: marked DEPRECATED guard | n/a | n/a | **DEPRECATED** |
| `zangetsu/scripts/rescan_legacy_with_new_gates.py` | rescan legacy archive with current gates | offline | none (read-only) | YES | NO |
| `zangetsu/services/factor_zoo.py` | factor zoo reporting | per VERSION_LOG: DEPRECATED guard | n/a | n/a | **DEPRECATED** |
| `zangetsu/services/alpha_discovery.py` | run every */30 min via cron — factor discovery | online via cron | DB? | n/a | per VERSION_LOG: DEPRECATED guard |

## 2. Raw Alpha Sources

| Path | Contents |
| --- | --- |
| `~/strategic-research/alpha_zoo/` | subdirs `arxiv/`, `bigquant/`, plus 7 sources of formulas (per prior orders) |
| `~/strategic-research/worldquant_101/alphas_raw.md` | 15.9 KB markdown, 101 alpha formulas |
| `~/strategic-research/worldquant_101/kakushadze_2015.pdf` | source paper |

These are **READ-ONLY research artifacts** — not directly executed.

## 3. Offline Replay Scripts (from prior orders)

| Script | Purpose |
| --- | --- |
| `/tmp/0-9wzr-offline-replay.py` (PR #39) | offline alpha-zoo replay — 30 formulas × 5 syms, 0 DB connection |
| `/tmp/0-9wch-replay.py` (PR #40) | calibration matrix replay — 663 cells, 0 DB connection |
| `/tmp/0-9wch-analyze.py` (PR #40) | aggregate analyzer over JSONL outputs |

These scripts proved the offline-replay-only methodology. **Safe for inspection and re-use.**

## 4. Dry-Run Capability

| Tool | Dry-run support |
| --- | --- |
| `alpha_zoo_injection.py` | flag parsed (`--dry-run-one`) but BODY UNIMPLEMENTED — must NOT be relied upon |
| `seed_101_alphas*.py` | DEPRECATED — must not be run |
| `factor_zoo.py` | DEPRECATED |
| Custom offline replays under `/tmp/` | YES — by construction (no DB connection) |

→ **No production-ready dry-run path exists for alpha injection.** Any cold-start that wants to inject formulas must either:
1. Build a proper dry-run mode in `alpha_zoo_injection.py`, OR
2. Use offline replay scripts to validate, then introduce a separate, signed governance order to do the real injection through `champion_pipeline_staging` after the v0.7.1 migration is applied

## 5. Validation Bypass Risk

| Tool | Bypasses validation? |
| --- | --- |
| `alpha_zoo_injection.py` | writes to staging; relies on `admission_validator()` to gate (function MISSING — Phase 7) → **WOULD CURRENTLY BYPASS VALIDATION** |
| `seed_101_alphas.py` (deprecated) | n/a |
| Offline replays | NO (no DB writes) |

→ **`alpha_zoo_injection.py` is currently UNSAFE to run** because the validator function does not exist. Without `admission_validator()`, any staging insert that succeeds would be unvalidated.

## 6. Per-Tool Classification

| Tool | Class |
| --- | --- |
| `alpha_zoo_injection.py` | **TOOL_REQUIRES_SAFETY_REFACTOR** (no working dry-run + missing validator function) |
| `seed_101_alphas.py` | **TOOL_DEPRECATED_BLOCKED** (DEPRECATED guard) |
| `seed_101_alphas_batch2.py` | **TOOL_DEPRECATED_BLOCKED** |
| `rescan_legacy_with_new_gates.py` | **TOOL_SAFE_INSPECT_ONLY** |
| `factor_zoo.py` | **TOOL_DEPRECATED_BLOCKED** |
| `alpha_discovery.py` | TOOL_REQUIRES_SAFETY_REFACTOR (per VERSION_LOG: DEPRECATED guard, but still cron-runs every */30 min — concerning) |
| `/tmp/*-replay.py` (PR #39, #40) | **TOOL_SAFE_OFFLINE_REPLAY** |
| `/tmp/*-analyze.py` | TOOL_SAFE_INSPECT_ONLY |

## 7. Known Constraints (per order)

| Constraint | Honored? |
| --- | --- |
| `seed_101_alphas.py` is deprecated; do not run | ENFORCED — has DEPRECATED guard |
| `alpha_zoo_injection.py` has no working dry-run | CONFIRMED |
| alpha_zoo injection blocked | ENFORCED via PR #41 NG conditions |
| Cold-start must go through upgraded validation contract | NOT YET POSSIBLE — contract upgrade pending (PR #41 next-order recommendation) |

## 8. Phase 9 Verdict

→ **Cold-start tooling is not yet ready.**

Critical gaps:
- `alpha_zoo_injection.py` lacks a working dry-run AND its target validator does not exist
- `alpha_discovery.py` runs every 30 min via cron despite DEPRECATED guard — should be examined and confirmed harmless or disabled
- The validation contract upgrades (NG2/NG3 from PR #41) are prerequisites
- The DB schema (Phase 7) is a prerequisite

Until those gaps close, cold-start tooling can only be exercised in OFFLINE REPLAY mode (TOOL_SAFE_OFFLINE_REPLAY).
