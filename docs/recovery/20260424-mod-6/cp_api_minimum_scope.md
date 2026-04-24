# cp_api Minimum Scope — MOD-6 Phase 3 (Prereq 1.6)

- **Scope**: Define the MINIMUM VIABLE cp_api skeleton for Phase 7 entry. Maximally conservative: read-only surface, no runtime authority, no write endpoints, no control-plane takeover.
- **Actions performed**:
  1. Enumerated Phase 7 entry requirements for cp_api from `phase7_entry_pack.md §1.6` + `modular_target_architecture.md §3 L1`.
  2. Identified MINIMUM vs FULL scope split.
  3. Authored skeleton implementation (`server.py` + `requirements.txt` + `cp-api.service` systemd unit).
  4. Deployed + started on Alaya; verified operational.
- **Evidence path**:
  - `zangetsu/control_plane/cp_api/server.py` (committed)
  - `zangetsu/control_plane/cp_api/requirements.txt` (committed)
  - `zangetsu/control_plane/cp_api/cp-api.service` (committed; active on Alaya via `/etc/systemd/system/cp-api.service` symlink)
  - `/var/log/zangetsu/cp_api/audit.log` (Alaya filesystem; not committed)
- **Observed result — minimum vs full**:

| Feature | Minimum (MOD-6 skeleton) | Full (Phase 7+) |
|---|---|---|
| `/health` endpoint | ✅ LIVE | ✅ |
| Bearer-token auth | ✅ LIVE (env-provided CP_API_TOKEN) | ✅ (key rotation + revocation) |
| `GET /api/control/mode` | ✅ (returns hard-coded "safe") | writeable via authorized actors |
| `GET /api/control/params` | ✅ (returns empty list) | populated from `control_plane.parameters` Postgres schema |
| `GET /api/control/modules` | ✅ (returns empty list) | populated via CI/CD sync from `zangetsu/module_contracts/*.yaml` |
| `GET /api/control/rollout/{subsystem}` | ✅ (returns OFF for all) | real rollout tier from `control_plane.rollout` |
| Write endpoints (`POST/PUT/DELETE`) | ❌ BLOCKED by write-safety middleware (405) | authorized propose/approve/kill flows |
| Postgres `control_plane.*` schema | ❌ not created | created; migrations applied |
| pg_notify / Redis pub/sub for CP change events | ❌ not wired | `cp_notifier` module live |
| Audit log | ✅ file-based (`/var/log/zangetsu/cp_api/audit.log`) | Postgres append-only table; AKASHA mirror |

- **Forbidden changes check**:
  - NO runtime authority: service cannot stop/start other services, cannot write any parameter, cannot influence runtime behavior of any existing system.
  - NO production mutation: all endpoints read-only; write-safety middleware returns 405 on any non-GET.
  - NO thresholds / gates / arena touch.
  - Service runs as `j13` user (non-root); systemd unit grants no privileged capabilities.
- **Residual risk**:
  - Service binds `127.0.0.1:8773` (loopback only). Not exposed externally; requires SSH or Caddy reverse-proxy for external reach. Current state: loopback-only — no external attack surface.
  - `CP_API_TOKEN` stored in `.env` with mode 600, owned by j13. Leak would allow read access to empty-registry endpoints — low-impact in skeleton stage.
- **Verdict**: MINIMUM SCOPE IS EXACTLY RIGHT — satisfies Phase 7 entry prerequisite 1.6 ("cp_api skeleton operational") without reaching any of the "runtime takeover" failure modes called out by 0-8 non-negotiable rules 4 + 7.
