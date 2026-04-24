# State Snapshot Artifact Spec — MOD-6 Phase 4 (Prereq 1.7)

- **Scope**: Canonical artifact layout for snapshot JSON + diff Markdown, including freshness + ownership rules. Operationalizes `pre_post_snapshot_spec.md v1` (MOD-5 design).
- **Actions performed**:
  1. Finalized filesystem layout for snapshots + diffs.
  2. Defined filename convention + ownership tagging.
  3. Specified freshness windows per use case.
  4. Validated via MOD-6 Phase 4 live run.
- **Evidence path**:
  - Snapshot directory: `docs/governance/snapshots/<ISO-ts>-<purpose>-<actor>.json`
  - Diff directory: `docs/governance/diffs/<purpose>.md`
  - MOD-6 Phase 4 artifacts listed in `controlled_diff_live_run_report.md §Evidence`
- **Observed result — spec**:

**Snapshot filename format**: `<ISO-ts-compact>-<purpose>-<actor>.json`
- ISO ts compact: `YYYYMMDDTHHMMSSZ` (UTC; no colons for safe filenames)
- Purpose: kebab-case tag (e.g. `mod6-pre`, `rollback-rehearsal-post`)
- Actor: `<agent-or-human>@<context>` with `[^a-zA-Z0-9_-]` → `_` (filesystem-safe)

**Snapshot JSON schema (v1)**: Matches `pre_post_snapshot_spec.md §1-§2` exactly:
- `schema_version`, `captured_at`, `captured_by`, `purpose`, `surfaces`, `sha256_manifest`

**Diff filename format**: `<purpose>.md` or `<pre_ts>_to_<post_ts>-<purpose>.md`

**Diff content**: Markdown with `## Classification`, zero/explained/forbidden field lists, overall verdict.

**Freshness windows**:
- Gate-A classification evidence: snapshot within last 24h
- Phase 7 entry legality check: snapshot within last 1h
- Per-module rollback rehearsal: snapshot within last 7 days
- Hourly automation (Phase 7): snapshot every 1h, retained 30 days

**Ownership**:
- Manual captures: owned by capturing actor (e.g., Claude Lead during MOD-N)
- Future cron captures: owned by `gov_reconciler` (Phase 7)

**Retention (Phase 7)**:
- Last 30 days: all hourly snapshots
- Beyond 30 days: monthly archival to AKASHA `segment=governance_snapshot_archive`
- Snapshots referenced by an active classification memo: retained until memo archived

- **Forbidden changes check**: Spec is pure documentation + filename conventions. No runtime mutation. File naming is operator-discipline; script-enforced via `capture_snapshot.sh` generating names per spec.
- **Residual risk**:
  - Operator could manually write snapshot files with incorrect schema — protection: `diff_snapshots.py` requires `.get('surfaces', {})` so malformed snapshots yield empty diffs (defensive).
  - Manual captures can skew freshness — phase 7 cron eliminates.
- **Verdict**: Artifact spec is CONCRETE + VERIFIED by MOD-6 live run. Prerequisite 1.7 operationalization has a defined evidence storage path.
