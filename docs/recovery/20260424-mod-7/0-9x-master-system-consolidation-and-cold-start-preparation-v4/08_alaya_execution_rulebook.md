# 42-08 — Alaya-Only Execution Rulebook

**Order**: TEAM ORDER 0-9X-MASTER-SYSTEM-CONSOLIDATION-AND-COLD-START-PREPARATION-v4
**Track**: G — Alaya-Only Execution Rulebook
**Date**: 2026-04-27
**Status**: GOVERNANCE — binding for all future ZANGETSU runtime orders
**Scope**: All cold-start, optimization, validation, CANARY, and production decisions

---

## Preamble

ZANGETSU has, on multiple occasions, suffered from a class of failure where a
local-Mac result, an outdated branch, or a stale schema snapshot was treated as
authoritative for runtime change. This rulebook eliminates that class. Alaya is
the only environment whose state can authorize a runtime change. Mac is a
mirror used for editing, review, and dispatch — never for authorization.

Eight rules follow. Each rule has a normative statement, an example of correct
application, and a counter-example showing the failure mode it prevents.

---

## Rule 1 — Alaya is the runtime source of truth. Mac is mirror only.

**Statement**: All runtime state — process liveness, DB schema, parameter
matrices, log files, cron jobs, Docker containers — exists exclusively on Alaya
(`100.123.49.102`, repo `/home/j13/j13-ops`). Mac (`/Users/a13/dev/j13-ops`) is
a working mirror used to compose commits, review diffs, and dispatch CI; it
holds no authoritative runtime state.

**Example (correct)**: To verify A1 worker liveness, SSH Alaya and inspect
`pgrep -af zangetsu_a1` plus `/tmp/zangetsu_a1_w*.log`. Mac mirror is not
queried.

**Counter-example (forbidden)**: "I ran the validator on Mac and it returned
0 forbidden, so the runtime is clean." — REJECTED. The Mac validator binds
to Mac files. Runtime cleanliness must be re-asserted against Alaya HEAD and
Alaya DB.

---

## Rule 2 — No runtime change valid without Alaya verification at execution time.

**Statement**: A cold-start, optimization result, parameter promotion, CANARY
flip, or production order is invalid unless verified, at the moment of
execution, against:

- Alaya HEAD (must equal `origin/main`)
- DB inventory snapshot (taken on Alaya, against `deploy-postgres-1`)
- Parameter source-of-truth matrix snapshot (taken on Alaya)

Verification artifacts older than the most recent commit on `origin/main` are
stale and must be regenerated.

**Example (correct)**: Before flipping CANARY ON, the operator pulls Alaya
HEAD, re-runs the schema inventory, re-checks the parameter matrix, and
confirms all three match the pre-flip plan recorded in the order.

**Counter-example (forbidden)**: "We did the schema inventory on Friday, the
flip is Monday, schema hasn't changed." — REJECTED. Inventory must be
regenerated at flip time. The cost is a 30-second SQL snapshot; the value is
catching a Saturday hot-fix that broke the matrix.

---

## Rule 3 — Required preflight fields for every future order.

**Statement**: Every order that authorizes runtime change must carry, in its
preflight section, the following nine fields. A missing field invalidates the
order; an order with missing fields cannot authorize runtime change.

| # | Field | Acceptance |
|---|-------|------------|
| 1 | Alaya HEAD SHA | Must equal `origin/main` HEAD at preflight time |
| 2 | Working tree dirty state | Clean except runtime artifacts (`/tmp/zangetsu_*.log`, `*.pid`, `engine.jsonl`) |
| 3 | DB schema inventory snapshot | Live SQL output capturing all v0.7.x objects |
| 4 | Parameter source-of-truth matrix | Live snapshot listing every tunable parameter and its authoritative file |
| 5 | Validation contract status | All 4 gates active OR explicit doc of which is missing and why |
| 6 | Controlled-diff result | `0 forbidden` |
| 7 | Gate-A pass | Latest run on `origin/main` HEAD = SUCCESS |
| 8 | Gate-B pass | Latest run on `origin/main` HEAD = SUCCESS |
| 9 | Telegram Thread 356 final notification msg_id | Numeric msg_id on chat `-1003601437444`, thread `356` |

**Example (correct)**: A CANARY order's preflight section lists all 9 fields,
each filled with a value collected within the past 30 minutes against Alaya
HEAD `9f6dc60`.

**Counter-example (forbidden)**: An order shows "Gate-A: pass (last week)" —
REJECTED. Gate status must be evaluated against the current HEAD, not a prior
HEAD.

---

## Rule 4 — Local-only Mac results CANNOT authorize runtime change.

**Statement**: Any test, validator, backtest, or schema check executed solely
on Mac is informational only. It cannot serve as evidence in Rule 3 fields. If
a Mac result is to be used, it must be re-executed on Alaya, and the Alaya
output is the artifact of record.

**Example (correct)**: Operator runs the optimizer on Mac for fast iteration,
then on the final candidate set re-runs the same script on Alaya and records
the Alaya output in `docs/recovery/`.

**Counter-example (forbidden)**: "Backtest on Mac shows Sharpe 1.4, promote to
CANARY." — REJECTED. Mac backtest is informational. Re-run on Alaya against
Alaya DB inventory; Alaya output is what authorizes the promotion.

---

## Rule 5 — No CANARY without live `arena_batch_metrics` non-zero. No production without explicit production order.

**Statement**: A CANARY flip requires positive evidence of candidate flow at
flip time: at least one event in `arena_batch_metrics` within the last 5
minutes, with non-zero candidate count. A production flip requires a separate,
explicit production order — CANARY success does not implicitly authorize
production.

**Example (correct)**: Operator confirms `SELECT count(*) FROM arena_batch_metrics WHERE event_ts > now() - interval '5 minutes'`
returns `>= 1` with non-zero candidates, then flips CANARY. Production flip is
deferred pending separate order issuance.

**Counter-example (forbidden)**: "A1 workers are alive, flip CANARY." —
REJECTED. Worker liveness does not imply candidate flow. Empty pipeline ⇒
CANARY would observe nothing.

**Counter-example (forbidden)**: "CANARY ran 24h with no incident, promote to
production." — REJECTED unless a production order exists. CANARY duration is
a necessary, not sufficient, condition.

---

## Rule 6 — Optional preflight script: `~/j13-ops/scripts/alaya_preflight.sh` (DESIGN ONLY).

**Statement**: A preflight automation script may be designed but must NOT be
implemented under this order. The design is captured in
`/tmp/alaya_preflight_design.md`. The script, when later implemented, must
fail-closed if any of the following are detected:

- Alaya HEAD ≠ `origin/main` HEAD
- Working tree dirty (excluding runtime artifacts allowlist)
- DB schema inventory does not match expected v0.7.x manifest
- Parameter matrix file missing or contains forbidden TODO/FIXME markers
- Controlled-diff returns non-zero forbidden count

The script is an aid, not a substitute for human verification of Rule 3 fields.
A green script run does not autopromote any order.

**Example (correct)**: Operator runs `alaya_preflight.sh`, exit 0, then still
manually fills the 9-field block in the order. Script output is attached as
evidence.

**Counter-example (forbidden)**: "Script returned 0, skipping the 9-field
block." — REJECTED. Script is necessary-not-sufficient.

---

## Rule 7 — Acceptance criteria for "Alaya verified" stamp on any future order.

**Statement**: A future order may carry the `[ALAYA-VERIFIED]` stamp only when
the 9 fields of Rule 3 are filled, the values were collected against Alaya
HEAD at preflight time, and the evidence is mirrored to `docs/recovery/`. The
stamp is applied by the operator who collected the evidence and is
co-signed (in the commit trailer) by a second reviewer (Gemini or human) who
re-checked the live values.

**Stamp form**:

```
[ALAYA-VERIFIED] head=<sha7> ts=<utc-iso> by=<operator> reviewed-by=<reviewer>
```

**Example (correct)**: `[ALAYA-VERIFIED] head=9f6dc60 ts=2026-04-27T00:12:33Z by=claude reviewed-by=gemini`

**Counter-example (forbidden)**: A stamp with no `head=` or `ts=` field, or
with a `head=` value that does not match `origin/main` at the time of stamp
application — REJECTED.

---

## Rule 8 — Evidence preservation: `docs/recovery/` is non-deletable, append-only.

**Statement**: All preflight evidence — schema inventories, parameter
snapshots, controlled-diff outputs, Gate-A/Gate-B run logs, Telegram msg_id
references, CANARY decision records — are written under `docs/recovery/` with
a timestamped filename and never deleted, overwritten, or rewritten. Errors in
prior evidence are corrected by appending a new evidence file that explicitly
references and supersedes the prior one.

**File naming**: `docs/recovery/YYYYMMDD-HHMM-<order>-<artifact>.md` (or
`.json`, `.txt` as appropriate).

**Example (correct)**: A schema inventory taken at preflight is saved as
`docs/recovery/20260427-0012-42-08-schema-inventory.json`. A later inventory
correcting an omission is saved as a new file referencing the earlier one;
the earlier file is left in place.

**Counter-example (forbidden)**: `git rm docs/recovery/20260420-1530-old-canary-evidence.md`
— REJECTED. Pre-receive hook and CI must block deletion under
`docs/recovery/`.

---

## How to mark a future order Alaya-verified — Operator Checklist

Run this checklist on Alaya, capturing every output to `docs/recovery/` with a
shared timestamp prefix:

- [ ] `git -C /home/j13/j13-ops fetch origin && git -C /home/j13/j13-ops rev-parse HEAD` matches `git -C /home/j13/j13-ops rev-parse origin/main`
- [ ] `git -C /home/j13/j13-ops status --porcelain` empty after stripping the runtime-artifact allowlist
- [ ] DB inventory: `psql -c "\dt+"` and `\dv+`, `\df+` against `deploy-postgres-1`, output saved
- [ ] Parameter source-of-truth matrix snapshot saved (per-parameter file, line, value)
- [ ] Validation contract: 4 gates listed (RuntimeBudget / SchemaContract / ParamMatrix / FreshnessGate); each is `ACTIVE` or has documented `MISSING-because-<reason>`
- [ ] Controlled-diff: `scripts/controlled_diff.sh` (or its CI equivalent) reports `forbidden_count=0`
- [ ] Gate-A: latest run on `origin/main` HEAD = SUCCESS, run URL captured
- [ ] Gate-B: latest run on `origin/main` HEAD = SUCCESS, run URL captured
- [ ] CANARY-only check (if applicable): `arena_batch_metrics` last-5-minute non-zero candidate count
- [ ] Telegram Thread 356 final notification posted; msg_id captured
- [ ] Stamp applied: `[ALAYA-VERIFIED] head=<sha7> ts=<utc-iso> by=<operator> reviewed-by=<reviewer>`
- [ ] Reviewer (Gemini or human) re-checked all 9 values live and co-signed in commit trailer
- [ ] All evidence committed under `docs/recovery/<YYYYMMDD-HHMM>-<order>-*` and pushed (signed, ED25519)

If any item fails, the stamp MUST NOT be applied. The order remains
Alaya-unverified and cannot authorize runtime change.

---

## Cross-references

- Companion: `/tmp/alaya_execution_rulebook.md` (standalone copy referenced by AC)
- Companion: `/tmp/alaya_preflight_design.md` (Rule 6 script design, not implemented)
- Constitution: CLAUDE.md §17.1 (`<project>_status` VIEW), §17.6 (stale-service check)
- Validation: Gate-A / Gate-B CI workflows (see `.github/workflows/`)
- Branch protection: 5 flags ON (enforce_admins, required_signatures, required_linear_history, allow_force_pushes=false, allow_deletions=false)
- Signing key: `/home/j13/.ssh/id_ed25519_signing.pub`
