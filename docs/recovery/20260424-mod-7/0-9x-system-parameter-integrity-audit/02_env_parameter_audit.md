# 02 — Environment Variable and Secret Presence Audit

## 1. /home/j13/.env.global Contents (keys only — values redacted)

```
BINANCE_API_KEY        present, redacted
BINANCE_SECRET_KEY     present, redacted
ZV5_DB_PASSWORD        present, redacted
```

→ **Only 3 secret keys in .env.global.** No `ALPHA_*`, `J01_*`, `APPLY_*`, `CANARY_*` overrides.

## 2. Required Variables Cross-Check

| Variable | Required by | Present? |
| --- | --- | --- |
| `ZV5_DB_PASSWORD` | `zangetsu/config/settings.py:99` (no fallback — fails import if absent) | YES |
| `BINANCE_API_KEY` | live execution (not used in current arena pipeline) | YES |
| `BINANCE_SECRET_KEY` | live execution | YES |
| `ALPHA_N_GEN`, `ALPHA_POP_SIZE`, `ALPHA_TOP_K`, `ALPHA_ENTRY_THR`, `ALPHA_EXIT_THR`, `ALPHA_MIN_HOLD`, `ALPHA_COOLDOWN`, `A1_WORKER_SEED` | `arena_pipeline.py` env reads | **NOT SET** — defaults used |
| `J01_*` strategy threshold overrides | `j01/config/thresholds.py` (loader expectation) | **NOT SET** — hardcoded defaults used |
| `APPLY_MODE`, `CANARY_MODE` | (none defined) | NOT SET (correct) |

## 3. Default Values In Use (no env override)

| Parameter | Source | Default | Effective value |
| --- | --- | --- | --- |
| `ALPHA_N_GEN` | `arena_pipeline.py:751` | 20 | **20** |
| `ALPHA_POP_SIZE` | line 752 | 100 | **100** |
| `ALPHA_TOP_K` | line 753 | 10 | **10** |
| `ALPHA_ENTRY_THR` | line 754 | 0.80 | **0.80** |
| `ALPHA_EXIT_THR` | line 755 | 0.50 | **0.50** |
| `ALPHA_MIN_HOLD` | line 756 | 60 | **60** |
| `ALPHA_COOLDOWN` | line 757 | 60 | **60** |

→ **No silent env override on any parameter.** All values come from source defaults.

## 4. Special Focus — Order's "No Silent Override" Requirement

| Param | Risk | Result |
| --- | --- | --- |
| `cost_bps` | env override possible? | NO — `cost_bps = cost_model.get(sym).total_round_trip_bps` (line 877); no env knob |
| `ENTRY_THR` | env override possible? | YES (`ALPHA_ENTRY_THR`) — NOT SET; default 0.80 |
| `MAX_HOLD_BARS` | env override possible? | NO — read from `j01/config/thresholds.py:MAX_HOLD_BARS = 120` (no env hook) |
| `TRAIN_SPLIT_RATIO` | env override possible? | NO — hardcoded `0.7` (line 283) |
| `A2_MIN_TRADES` | env override possible? | NO — hardcoded `25` (`arena_gates.py:48`) |
| APPLY mode | env-toggleable? | absent — no APPLY mode anywhere |
| CANARY mode | env-toggleable? | absent — no CANARY mode env hook |

→ **No hidden override. No CANARY/APPLY toggle.**

## 5. Secret Exposure Risk

| Risk | Status |
| --- | --- |
| Secrets printed in commits | NONE |
| Secrets in logs | not observed |
| `.env.global` in git | NO (gitignored) |
| `.env.global` permission | 0644 (per stat — verified during audit) — readable by j13 only at the OS level |

## 6. Classification

| Verdict | Match? |
| --- | --- |
| **ENV_OK** | **YES** |
| ENV_MISSING_REQUIRED | NO |
| ENV_OVERRIDE_CONFLICT | NO |
| ENV_SECRET_EXPOSURE_RISK | NO |
| ENV_UNKNOWN | NO |

→ **Phase 2 verdict: ENV_OK.** Required secrets present. No silent override. No CANARY/APPLY backdoor.
