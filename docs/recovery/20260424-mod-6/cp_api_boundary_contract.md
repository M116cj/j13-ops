# cp_api Boundary Contract — MOD-6 Phase 3 (Prereq 1.6)

- **Scope**: Explicit boundary: what cp_api MAY do, MAY NOT do, and what remains CONSPICUOUSLY ABSENT in the skeleton.
- **Actions performed**:
  1. Enumerated all endpoints in skeleton `server.py`.
  2. Annotated each with capability class.
  3. Enumerated features INTENTIONALLY ABSENT to prevent runtime takeover.
- **Evidence path**:
  - `zangetsu/control_plane/cp_api/server.py` (all code and middleware)
  - `cp-api.service` systemd unit (user=j13, no capabilities beyond default)
- **Observed result**:

MAY DO (skeleton):
- Serve `/health` (liveness probe, no auth)
- Serve read-only GETs for `/api/control/{mode,params,params/{key},modules,rollout/{subsystem}}` with bearer token
- Append audit rows to `/var/log/zangetsu/cp_api/audit.log`

MAY NOT DO (enforced by code):
- Accept any POST/PUT/DELETE/PATCH — middleware returns 405
- Write to any Postgres table — skeleton has no DB connection
- Modify any file outside its audit log directory
- Execute any subprocess — skeleton imports no subprocess module
- Make outbound network calls beyond what FastAPI + uvicorn need at bind time
- Influence any existing service (Calcifer, arena, miniapp, d-mail) — no service-management code present

INTENTIONALLY ABSENT (Phase 7 dependencies):
- Write endpoints (propose, approve, reject, kill_switch, mode_change)
- Decision-rights matrix enforcement
- `control_plane.*` Postgres schema
- pg_notify / Redis pub/sub for change-event fan-out
- cp_worker_bridge library (worker-side consumer — M9 mandatory module, not yet implemented)
- gov_contract_engine integration (PolicyVerdict producer)
- Rate-limiting at API gateway level (delegated to consumer-side `cp_worker_bridge` rate_limit schema)

- **Forbidden changes check**: Skeleton does NOT implement ANY of the "runtime takeover" capabilities that 0-8 non-negotiable rules 4 + 7 prohibit. Service can be `systemctl stop`-ped at any moment with zero impact on any existing live system (arena frozen remains frozen, Calcifer continues, miniapps unaffected).
- **Residual risk**:
  - If a future well-intentioned contributor adds a write endpoint or DB connection WITHOUT updating this boundary contract + without going through Phase 7 gate process, it could expand authority silently. Mitigation: Gate-B workflow on any `zangetsu/control_plane/**` path + Controlled-Diff surface SHA detects changes.
  - Audit log is file-based — log rotation not yet configured. Long-term the log could grow unbounded; accepted for MOD-6 (Phase 7 adds rotation).
- **Verdict**: BOUNDARY IS PRECISE AND ENFORCEABLE. cp_api skeleton embodies the correct minimum for prerequisite 1.6 without overreaching into runtime control.
