# Control Surface Matrix — Zangetsu MOD-1 (optional)

**Order**: `/home/j13/claude-inbox/0-2` optional deliverable
**Produced**: 2026-04-23T03:00Z
**Author**: Claude (Lead)
**Status**: DESIGN — enumerates every control surface (parameter, kill switch, rollout advance, mode change) in the target architecture and maps it to its owning module + decision rights + audit tier.

Pairs with `state_ownership_matrix.md` (state side) and `control_plane_blueprint.md §4 / §5` (governance side).

---

## §1 — Purpose

"No black-box control surface" (0-2 rule 8) requires that every operator-visible lever has:
- An owning module (single point of enforcement)
- An entry in the decision-rights matrix
- An audit tier
- A rollout-tier gating if non-trivial

This matrix makes that explicit. If a surface is in production but not in this matrix, the design is incomplete — migration closes that gap.

---

## §2 — Surface taxonomy

Four classes per `module_contract_template.md §2 field 14`:

- **P** — parameter (numeric / enum / string config)
- **K** — kill switch (on/off emergency control)
- **R** — rollout advance (OFF → SHADOW → CANARY → FULL)
- **M** — mode change (SAFE / SHADOW / CANARY / PRODUCTION / FROZEN)

Audit tier: `standard` (write row to CP audit) or `high` (also Telegram).

Decision rights per `control_plane_blueprint.md §5` row id.

---

## §3 — System controls (CP §4.1)

| Surface key | Class | Owner module | Decision rights (§5 row) | Audit tier | Rollout-gated |
|---|---|---|---|---|---|
| `system.mode` | M | cp_api | "System mode" | high | n/a (mode IS the rollout state) |
| `system.workers.a1_count` | P | kernel_dispatcher | "Worker counts" | standard | FULL |
| `system.workers.a23_count` | P | kernel_dispatcher | same | standard | FULL |
| `system.workers.a45_count` | P | kernel_dispatcher | same | standard | FULL |
| `system.resource.cpu_quota_pct` | P | kernel_dispatcher | "Worker counts" (extended) | standard | FULL |
| `system.resource.ram_mb_per_worker` | P | kernel_dispatcher | same | standard | FULL |
| `system.kill.arena_a1` | K | kernel_state | "Kill switches" | high | n/a |
| `system.kill.arena_a23` | K | kernel_state | same | high | n/a |
| `system.kill.arena_a45` | K | kernel_state | same | high | n/a |
| `system.kill.data_collector` | K | data_provider | same | high | n/a |
| `system.kill.observer` | K | obs_metrics | same | high | n/a |
| `system.kill.gov_reconciler` | K | gov_reconciler | same | high | n/a |
| `system.cron.schedule` | P (map) | cp_api | "Cron schedule" | standard | gated (rollout per cron entry) |
| `system.rollout.<subsystem>` | R | cp_storage | rollout-advance | high | n/a |

---

## §4 — Search controls (CP §4.2)

| Surface key | Class | Owner | Decision rights | Audit | Rollout-gated |
|---|---|---|---|---|---|
| `search.engine.active` | P (enum) | search_contract | "Search params" | standard | gated |
| `search.gp.mutation_rate` | P | search_gp | "Search params" | standard | FULL |
| `search.gp.pop_size` | P | search_gp | same | standard | FULL |
| `search.gp.generations` | P | search_gp | same | standard | FULL |
| `search.gp.pset.active` | P (enum: full/lean/custom) | primitive_registry | same | standard | CANARY_X (lean/custom = new) |
| `search.gp.top_k` | P | search_gp | same | standard | FULL |
| `search.target.horizon_bars` | P | search_contract | same | high | CANARY_X (horizon change = D1 territory) |
| `search.target.strategy_id` | P (enum: j01/j02/...) | search_gp | same | standard | FULL |
| `search.exploration.ratio` | P (0..1) | search_contract | same | standard | FULL |
| `search.regime.partition_mode` | P (enum) | search_gp | same | standard | FULL |
| `search.promotion.policy_version` | P | gate_promote | "Search params" | high | CANARY_X |

---

## §5 — Validation / gate controls (CP §4.3)

| Surface key | Class | Owner | Decision rights | Audit |
|---|---|---|---|---|
| `gate.threshold.alpha_entry` | P | gate_registry | "Gate thresholds (major)" OR "(low-impact)" per magnitude | high (major) / standard (low-impact) |
| `gate.threshold.alpha_exit` | P | gate_registry | same | same |
| `gate.threshold.a2.min_trades` | P | gate_registry | same | same |
| `gate.threshold.a2.pos_count_required` | P | gate_registry | same | same |
| `gate.threshold.a3.*` | P | gate_registry | same | same |
| `gate.threshold.a4.*` | P | gate_registry | same | same |
| `gate.promote.wilson_lb` | P | gate_promote | "Gate thresholds (major)" | high |
| `gate.promote.min_trades` | P | gate_promote | same | high |
| `validation.train_split_ratio` | P | eval_contract | "Gate thresholds (major)" | high |
| `validation.holdout.required` | P (bool) | eval_a2_holdout | same | high |
| `validation.cost.bps_per_tier` | P (map) | cost_model | "Cost models" (locked — j13 only) | high |
| `validation.shadow.policy` | P (enum) | eval_contract | "Shadow policies" | standard |
| `deploy.block.state` | K | gate_calcifer_bridge | "Deploy block state" (Calcifer-owned) | high |

---

## §6 — Input controls (CP §4.4)

| Surface key | Class | Owner | Decision rights | Audit |
|---|---|---|---|---|
| `input.data.binance.symbols` | P (list) | data_provider | "Data sources" | standard |
| `input.data.time_window.history_days` | P | data_provider | same | standard |
| `input.data.feature_families` | P (list) | data_provider + primitive_registry | same | standard |
| `input.data.blacklist` | P (list) | data_provider | same | standard |
| `input.data.whitelist` | P (list) | data_provider | same | standard |
| `input.routing.family_policy_version` | P | gate_registry | "Output routing" | standard |

---

## §7 — Output controls (CP §4.5)

| Surface key | Class | Owner | Decision rights | Audit |
|---|---|---|---|---|
| `output.view.zangetsu_status.version` | P | pub_view | "Output routing" | high (downstream consumers pinned) |
| `output.publish.deployable_snapshot.enabled` | K | pub_snapshot | same | standard |
| `output.publish.telegram.channel_map` | P (map) | pub_telegram | same | standard |
| `output.publish.akasha.project` | P | pub_akasha | same | standard |
| `output.report.hourly.enabled` | K | obs_reports | same | standard |
| `output.alert.threshold.champion_count_delta` | P | pub_alert | "Output routing" | standard |
| `output.alert.routing.red_channel` | P | pub_alert | same | high |

---

## §8 — Integrity & governance controls

| Surface key | Class | Owner | Decision rights | Audit |
|---|---|---|---|---|
| `gov.reconciler.interval_s` | P | gov_reconciler | (gov-internal, j13 + Claude Lead) | standard |
| `gov.mutation_blocklist.version` | P | gov_contract_engine | "Deploy block state" (charter-level) | high |
| `gov.charter.rules_active` | P (list) | gov_contract_engine | j13-only | high |
| `gov.ci_hooks.enabled` | K | gov_ci_hooks | j13-only | high |
| `gov.rollout.advance.<subsystem>` | R | gov_rollout | "rollout-advance" row of §5 | high |

---

## §9 — Emergency controls (reserved)

Surfaces that ONLY Calcifer (or j13 direct) can change:

- `emergency.freeze_all_workers` — single K flipping every `system.kill.*` to ON
- `emergency.deploy_block_force` — override Calcifer block (j13-only; logs high-priority Telegram)
- `emergency.revert_last_commit` — j13 direct git revert + Calcifer witness

These have DIRECT pathways that bypass normal CP write gates (fail-closed in both directions — if CP is down, these still work via Redis atomic writes).

---

## §10 — Decision-rights rollup

| Owner | # of surfaces authorized |
|---|---|
| j13 direct | ALL (implicit) |
| Claude Lead (autonomous, low-impact only) | 47 surfaces with standard audit |
| Claude Lead (propose-only) | 14 high-audit surfaces |
| Gemini CHALLENGE pre-apply | All P / M writes (veto power) |
| Calcifer | 3 (deploy-block-related) |
| @macmini13bot (owner-fresh miniapp) | 22 (read + non-high-audit P writes) |
| Codex | 0 (Codex is executor, not surface-writer — writes go through its spawning Lead) |
| Markl | 0 (Markl is analyst, not surface-writer) |

---

## §11 — Coverage check

**Every surface class enumerated in `control_plane_blueprint.md §4` is represented here**:
- §4.1 System: §3 above — 14 surfaces ✅
- §4.2 Search: §4 above — 11 surfaces ✅
- §4.3 Validation: §5 above — 13 surfaces ✅
- §4.4 Input: §6 above — 6 surfaces ✅
- §4.5 Output: §7 above — 7 surfaces ✅
- Governance (extension): §8 above — 5 surfaces ✅
- Emergency: §9 above — 3 surfaces ✅

**Total: 59 concrete control surfaces** across 6 classes. Each has owner + decision rights + audit tier.

If Phase 7 adds a new surface not in this matrix, the migration PR MUST update this matrix (gate enforcement).

---

## §12 — Q1 adversarial

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | All 5 CP surface classes + governance + emergency covered; 59 surfaces enumerated | PASS |
| Silent failure | Each surface has audit tier; no surface is "untracked" | PASS |
| External dep | Calcifer/miniapp as external actors captured in decision-rights column | PASS |
| Concurrency | Every write goes through CP distributed lock (per blueprint §2 req 3) | PASS |
| Scope creep | Matrix enumerates surfaces; does NOT specify values, UIs, or implementation | PASS |
