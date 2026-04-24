# cp_api Skeleton Operational Report — MOD-6 Phase 3 (Prereq 1.6)

- **Scope**: Live-run evidence that the cp_api skeleton is operational on Alaya: systemd service active, authenticated read endpoints responsive, write-safety middleware rejects writes, audit log writing.
- **Actions performed**:
  1. `python3 -m venv .venv && pip install -r requirements.txt`
  2. `openssl rand -hex 32 > CP_API_TOKEN`; wrote `.env` with token (mode 600)
  3. `sudo cp cp-api.service /etc/systemd/system/`
  4. `sudo systemctl daemon-reload && sudo systemctl enable --now cp-api.service`
  5. `sleep 3` for steady state
  6. Live probes: `/health` (no auth), `/api/control/mode` (with token), `/api/control/mode` (without token → 401), `POST /api/control/mode` (with token → 405)
- **Evidence path**:
  - systemd: `sudo systemctl show cp-api -p MainPID,ActiveEnterTimestamp --value` → `1950393 / Fri 2026-04-24 01:38:06 UTC`
  - Health probe output (verbatim):
    ```json
    {"status":"ok","service":"cp_api","version":"0.1.0-skeleton-mod6",
     "started_at":"2026-04-24T01:38:06.267440+00:00",
     "runtime_authority":"none","write_endpoints":0,"skeleton":true}
    ```
  - Authenticated read (`/api/control/mode` with token):
    ```json
    {"mode":"safe","rationale":"skeleton service; no mode transitions implemented"}
    ```
  - Unauthenticated: `401`
  - POST attempt: `405`
  - Audit log tail:
    ```
    {"ts":"2026-04-24T01:38:09.129683+00:00","actor":"token","action":"read","target":"mode","outcome":"ok",...}
    {"ts":"2026-04-24T01:38:09.158606+00:00","actor":"curl/8.5.0","action":"POST","target":"/api/control/mode","outcome":"refused_write",...}
    ```
- **Observed result**:
  - Service state: **active** (systemd)
  - Health: **ok** (200)
  - Auth enforcement: **401** on missing/wrong bearer; **200** on valid bearer
  - Write-safety middleware: **405** on ALL non-GET requests
  - Audit trail: appending per request with actor + action + target + outcome
  - No evidence of runtime authority overreach
- **Forbidden changes check**:
  - Service runs on `127.0.0.1:8773` (loopback) — no external exposure
  - Non-GET requests universally rejected (verified)
  - Service user = `j13` (non-root)
  - No integration with arena, gates, thresholds, or existing live services
  - audit log `/var/log/zangetsu/cp_api/audit.log` is append-only (service never rewrites)
- **Residual risk**:
  - `CP_API_TOKEN` leakage would expose empty-registry reads (low impact)
  - If `control_plane.*` Postgres schema is later created without migration discipline, registry could desync — Phase 7 addresses with formal migration
  - `/var/log/zangetsu/cp_api/audit.log` is file-based, not Postgres — Phase 7 upgrade
- **Verdict**: cp_api SKELETON IS OPERATIONAL. All 4 probes pass. No write authority. Prerequisite 1.6 = **VERIFIED LIVE MET**.
