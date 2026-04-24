# Control Plane Blueprint — MOD-3 Amendment

**Order**: `/home/j13/claude-inbox/0-4` Phase 2 deliverable
**Produced**: 2026-04-23T07:48Z
**Supersedes**: `docs/recovery/20260423-mod-1/control_plane_blueprint.md` via delta amendment
**Amendment scope**: Formalize cp_worker_bridge M9 mandatory status + rollout-authority boundary + egress declaration for CP.

---

## 1. Amendment summary

| Change | Source |
|---|---|
| cp_worker_bridge promoted to mandatory module (M9) | R2-F3 HIGH |
| Add `POST /api/control/params?keys=a,b,c` batch-read endpoint | implied by M9 performance contract |
| Decision-rights §5 row for "rollout-advance" clarifies authority column = gov_rollout_authority | R2-F2 HIGH |
| Add §4.1 "CP Service execution_environment" declaration | R1b-F1 HIGH (template Field 15) |
| Add §10.1 clarification: CS-05 docker-exec mitigation scope is DETECTION only; Phase 7 ops hardening adds prevention | clarity; pre-existing gap |

## 2. §3.1 Deployment model — amended

Original §3.1 said:
- Single process, co-located with existing trusted host (Alaya).
- Exposed via HTTP API on an internal port (e.g. `:8773`), CLI client `zctl`, gRPC/event stream for worker subscribers (Phase 7 option).

MOD-3 clarification:
- `cp_worker_bridge` is NOT a separate process — it's an in-process library consumed by every worker (per `cp_worker_bridge_promotion_spec.md §3`).
- Workers call `cp_bridge.get()` → library makes HTTP request to cp_api locally (loopback).
- Event stream subscription via pg_notify OR Redis pub/sub (cp_notifier emits; cp_worker_bridge.subscribe() consumes).

## 3. §4 Functional scope — unchanged (still 5 surface classes A-E)

No MOD-3 change to the surface classes. Amendments apply only to ownership column (§5) and execution-environment (§4.1).

## 4. NEW §4.1 — CP Service execution_environment (per MOD-3 template amendment)

```yaml
execution_environment:
  permitted_egress_hosts:
    - "127.0.0.1:5432"       # Postgres (control_plane schema)
    - "127.0.0.1:6380"       # Redis (pub/sub + lock)
    - "100.123.49.102:8769"  # AKASHA (audit mirroring; optional)
  subprocess_spawn_allowed: false
  subprocess_permitted_binaries: []
  filesystem_write_paths:
    - "/var/log/zangetsu/cp/"
    - "/tmp/"                 # ephemeral only
  max_rss_mb: 512
  max_cpu_pct_sustained: 30
  requires_root: false
  requires_docker_group: false
  requires_sudo: false
```

Note: CP is Postgres + Redis consumer only. No external egress. Fail-closed on both.

## 5. §5 Decision-rights matrix — amended row

| Parameter class | j13 direct | Claude Lead (autonomous) | Gemini | Codex | Calcifer | Miniapp | **Ownership authority (NEW MOD-3 column)** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| System mode | YES | PROPOSE | CHALLENGE | n/a | n/a | YES (owner-fresh) | gov_contract_engine |
| Worker counts | YES | YES (within bounds) | CHALLENGE | n/a | n/a | YES (owner-fresh) | gov_contract_engine |
| Kill switches | YES | YES (own scope) | CHALLENGE | n/a | EMERGENCY | YES (owner-fresh) | gov_contract_engine |
| Search params | YES | YES (with ADR) | CHALLENGE | n/a | n/a | YES (with ADR) | gov_contract_engine |
| Gate thresholds (major) | YES | PROPOSE | CHALLENGE | n/a | n/a | NO direct | gov_contract_engine |
| Gate thresholds (low-impact) | YES | YES autonomous | CHALLENGE | n/a | n/a | YES (owner-fresh) | gov_contract_engine |
| Cost models | YES | NO (market truth) | CHALLENGE | n/a | n/a | NO | gov_contract_engine |
| Data sources | YES | PROPOSE | CHALLENGE | n/a | n/a | YES (read-only) | gov_contract_engine |
| Output routing | YES | YES | CHALLENGE | n/a | n/a | YES | gov_contract_engine |
| Deploy block state | CALCIFER-OWNED | n/a | n/a | n/a | YES | /unblock only | gate_calcifer_bridge (read) + Calcifer supervisor (write) |
| Cron schedule | YES | PROPOSE | CHALLENGE | n/a | n/a | NO | gov_contract_engine |
| Version bumps (feat/vN) | BUMP-SCRIPT | n/a | WITNESS | n/a | BLOCK (RED) | NO | gov_contract_engine + AKASHA witness |
| **Rollout-advance (NEW MOD-3)** | YES | PROPOSE (high-audit) | CHALLENGE | n/a | n/a | YES (owner-fresh + high-audit) | **gov_rollout_authority** |

New column "Ownership authority" specifies which module enforces; resolves R2-F2 by making the authority location unambiguous.

## 6. §7.1 Parameter entry — amended schema

Add two fields:

```yaml
parameter:
  # existing fields ...
  ownership_authority: <module_id>    # NEW MOD-3 — which module enforces this parameter's decision rights
  subscribers: [<module_id>, ...]     # NEW MOD-3 — which modules auto-receive change events via cp_worker_bridge
```

## 7. §8 API sketch — amended

Add batch-read endpoint:
```
GET /api/control/params?keys=a,b,c  → { a: {...}, b: {...}, c: {...} }  # MOD-3 addition
```

Rationale: cp_worker_bridge at worker startup often reads 10+ params at once. Batch endpoint reduces round-trips from 10 to 1 (per `cp_worker_bridge_promotion_spec §4`).

Add rollout-authority endpoints:
```
POST /api/control/rollout/{subsystem}/propose  → routed to gov_rollout_authority for PolicyVerdict
GET  /api/control/rollout/{subsystem}/history  → read rollout_audit
```

## 8. §9 Charter integration — unchanged

No MOD-3 change. §17.3 / §17.4 / §17.5 / §17.6 / §17.7 integration already captured.

## 9. §10 CS-05 docker-exec BLOCKER — amended scope clarification

§10 already states: "CP alone cannot solve CS-05. CP raises the cost of bypass by publishing expected DB-schema hash + reconciler cron comparing live vs expected + emitting alert."

MOD-3 clarification (formalizes what §10 hinted):
- **Detection**: gov_reconciler cron + cp_api schema-hash manifest comparison (Phase 7 implementation)
- **Alerting**: pub_alert emits RED Telegram via calcifer/notifier.py (mandatory per §10 v2 amendment)
- **Prevention**: OUT OF MOD-3 SCOPE — requires ops hardening (restrict docker group, MFA for docker exec, sudo audit) — flagged as Phase 7/ops-hardening work

Resolution of CS-05 remains **PARTIAL** (detection + alert present, prevention pending). This is consistent with MOD-1 state, just more explicit.

## 10. §11 Migration staging — unchanged (still 7 steps)

No MOD-3 change.

## 11. Resolution status

| Finding | Status |
|---|---|
| R2-F3 HIGH (cp_worker_bridge hidden dep) | RESOLVED via M9 promotion + §3.1 deployment clarification |
| R2-F2 HIGH (split-brain) | RESOLVED via §5 ownership column = gov_rollout_authority |
| R1b-F1 HIGH (egress blindness) | RESOLVED via §4.1 execution_environment declaration |

## 12. Label per 0-4 rule 10

- §2 §3.1 deployment: **PROBABLE** (design)
- §4.1 execution_environment: **PROBABLE** (design; VERIFIED when CP service deploys)
- §5 decision-rights amendment: **VERIFIED** (ownership column added; no behavioral change to existing rows)
- §7.1 schema: **PROBABLE** (additive, back-compatible)
- §9/§10: **VERIFIED** (alignment, not change)
