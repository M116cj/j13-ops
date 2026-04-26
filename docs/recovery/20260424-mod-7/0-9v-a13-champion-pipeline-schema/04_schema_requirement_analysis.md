# 04 — Schema Requirement Analysis

## 1. arena13_feedback.py SELECT-from-champion_pipeline Inventory

5 SELECT queries reference `champion_pipeline`:

### 1.1 Line 248 (survivor indicator counts)
```sql
SELECT regime, passport->'arena1'->'configs' AS configs,
       passport->'arena1'->>'alpha_expression' AS alpha_expression
FROM champion_pipeline
WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
  AND (passport->'arena1'->'configs' IS NOT NULL
       OR passport->'arena1'->'alpha_expression' IS NOT NULL)
  AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
  AND (engine_hash IS NULL OR engine_hash NOT LIKE '%_coldstart')
```

Columns referenced: `regime`, `passport (jsonb)`, `status`, `evolution_operator`, `engine_hash`.

### 1.2 Line 273 (failure indicator counts)
Columns: `regime`, `passport`, `status`, `engine_hash`, `evolution_operator`.

### 1.3 Line 341 (cool-off list)
Columns: `regime`, `status`, `engine_hash`, `updated_at`, `passport`, `evolution_operator`.

### 1.4 Line 359 (regime-indicator counts)
Same as 1.1 but with different aggregation.

### 1.5 Line 393 (TP survival counts)
Columns: `tp` (probably from passport extract), `tp_p`, `engine_hash`, `arena3_sharpe`, `evolution_operator`.

## 2. Required Column Coverage

| Column referenced | Available in `champion_pipeline_fresh` (per v0.7.1 schema) |
| --- | --- |
| regime | YES (text NOT NULL) |
| passport | YES (jsonb NOT NULL DEFAULT '{}') |
| status | YES (text NOT NULL DEFAULT 'ARENA1_READY' with valid_status_fresh CHECK) |
| evolution_operator | YES (text DEFAULT 'random') |
| engine_hash | YES (text NOT NULL) |
| updated_at | YES (timestamptz DEFAULT NOW()) |
| arena3_sharpe | YES (double precision) |
| id | YES (bigserial PRIMARY KEY) — useful as default ORDER BY |
| created_at | YES (timestamptz DEFAULT NOW()) |
| arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades | YES |
| arena2_*, arena4_*, arena5_last_tested | YES |
| elo_rating, elo_consecutive_first | YES |
| card_status | YES |
| family_id, family_tag, alpha_hash, deployable_tier, strategy_id | YES |
| 11 provenance fields | YES (engine_version, git_commit, config_hash, grammar_hash, fitness_version, patches_applied, run_id, worker_id, seed, epoch, created_ts) |

**All required columns are present in `champion_pipeline_fresh`.** No ALTER TABLE ADD COLUMN is needed.

## 3. arena13_feedback Filter Semantics

### Status filters
`'CANDIDATE'`, `'DEPLOYABLE'`, `'ARENA4_ELIMINATED'` — all present in v0.7.1 `valid_status_fresh` CHECK.

### Engine hash filters
- `engine_hash NOT LIKE '%_coldstart'` — exclude cold-start
- `engine_hash LIKE 'zv%'` — only post-v0.7.1 engine versions

`champion_pipeline_fresh` only stores Epoch B rows (per `valid_epoch_fresh` CHECK), which means it should mostly already have `zv*` engine hashes. Legacy archive holds Epoch A.

### Evolution operator filters
- exclude `'cold_seed%'`, `'gp_evolution'`

These are valid string values in `champion_pipeline_fresh.evolution_operator` (no CHECK constraint restricting values).

## 4. Should the VIEW Include `champion_legacy_archive` Too?

| Argument | Verdict |
| --- | --- |
| Pro UNION: A13 guidance might benefit from richer historical evidence | weak — feedback is forward-looking; legacy alphas are read-only and not promoted |
| Pro UNION: arena13_feedback queries with `engine_hash LIKE 'zv%'` may filter out legacy anyway | true |
| Con UNION: more rows in scan, slower queries | minor (1564 + 89 ≈ 1653 rows) |
| Con UNION: governance rule #1: "Epoch A rows are read-only and never promoted / ranked / deployed" | A13 only reads, doesn't promote — but UNION introduces ambiguity about which Epoch counts |
| Order's "smallest minimum schema" rule | favors fresh-only |
| Decision | **VIEW = SELECT * FROM champion_pipeline_fresh** (smallest, governance-safe). If A13 needs legacy data later, a separate enhancement order can change the VIEW to UNION ALL. |

## 5. Migration Shape Decision

```sql
CREATE OR REPLACE VIEW public.champion_pipeline AS
SELECT * FROM public.champion_pipeline_fresh;
```

| Property | Value |
| --- | --- |
| Idempotent | YES (`CREATE OR REPLACE`) |
| Destructive | NO (no DROP/TRUNCATE/DELETE/ALTER on tables) |
| Adds new tables / columns | NO |
| Compatible with arena13_feedback's 5 queries | YES (all referenced columns present in fresh) |
| Compatible with arena23_orchestrator design intent | YES (336-comment names `champion_pipeline VIEW`) |
| Risk to existing readers / writers | NONE (only adds a read-only view; underlying tables untouched) |

## 6. Index Decision

VIEW does not need its own indexes. Indexes on `champion_pipeline_fresh` (already present per v0.7.1: `idx_fresh_alpha_hash`, `idx_fresh_strategy_status`, `idx_fresh_strategy_tier`, `idx_fresh_status_regime`, `idx_fresh_lease`, `idx_fresh_elo`, `idx_fresh_run_id`, `uniq_fresh_alpha_hash`) are used through the VIEW.

## 7. Phase D Verdict

PASS. Schema requirement is fully derivable. No `BLOCKED_SCHEMA_AMBIGUOUS`. Migration is a single CREATE OR REPLACE VIEW.
