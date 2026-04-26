# 06 — Migration Apply Report

## 1. Apply Method

Executed via `zangetsu/.venv/bin/python /tmp/0-9v-a13-apply.py` under `bash -c 'set -a; . $HOME/.env.global; set +a; ...'`. The script performs a comment-stripping safety check, connects with psycopg2, executes the migration SQL inside a transactional block, and verifies the resulting object.

## 2. Pre-Apply Safety Audit

```
$ grep -Ei 'DR' || ECHO 'NO_DESTRUCTIVE_SQL_OUTSIDE_COMMENTS' (after stripping --comment lines)
NO_DESTRUCTIVE_SQL_OUTSIDE_COMMENTS

$ grep -Ei 'password|ZV5_DB_PASSWORD|postgres://' migration.sql
(no match)
```

→ No destructive SQL outside comments. No secret value in the migration file.

## 3. Apply Output (verbatim, no secret printed)

```
MIGRATION_APPLIED
champion_pipeline_view_exists=True
column_count=51
first_15_columns=id,regime,indicator_hash,status,lease_until,worker_id_str,retry_count,n_indicators,arena1_score,arena1_win_rate,arena1_pnl,arena1_n_trades,arena2_win_rate,arena2_n_trades,arena3_sharpe
row_count_via_view=89
```

## 4. Post-Apply Schema Inventory

```
TOTAL_TABLES=37   (+1 from 36 — the new VIEW)
CHAMPION_OBJECTS=[
  ['public', 'champion_legacy_archive',    'BASE TABLE'],
  ['public', 'champion_pipeline',          'VIEW'],          ← NEW
  ['public', 'champion_pipeline_fresh',    'BASE TABLE'],
  ['public', 'champion_pipeline_rejected', 'BASE TABLE'],
  ['public', 'champion_pipeline_staging',  'BASE TABLE'],
  ['public', 'champion_pipeline_v9',       'VIEW']
]
champion_pipeline_table_exists=True   (counted as a relation; it is a VIEW)
champion_pipeline_view_exists=True    ← the new object
champion_pipeline_fresh_exists=True
champion_legacy_archive_exists=True
champion_pipeline_fresh_row_count=89
champion_legacy_archive_row_count=1564
```

## 5. Hard-Ban Compliance

| Item | Status |
| --- | --- |
| Existing tables removed | NO |
| Rows removed | NO |
| Tables truncated | NO |
| Existing columns destructively altered | NO |
| Existing tables overwritten | NO |
| DB password modified | NO |
| Production data deleted | NO |
| Secret value printed | NO |
| Secret value committed | NO |

## 6. Phase G + H Verdict

PASS. `public.champion_pipeline` VIEW now exists with 51 columns and 89 underlying rows. No `BLOCKED_MIGRATION_APPLY_FAILED`.
