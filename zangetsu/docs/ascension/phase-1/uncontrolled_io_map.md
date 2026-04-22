# Zangetsu — Uncontrolled IO Map

**Program:** Ascension v1 Phase 1
**Date:** 2026-04-23
**Scope:** every IO path (inbound, outbound, cross-process, cross-host) that is NOT centrally governed today.
**Zero-intrusion:** documentation.

---

## §1 — Reading guide

"Uncontrolled" ≠ "broken". It means:
- no registry of permitted callers / consumers
- no schema version or contract
- no rate limit / backpressure
- no audit trail dedicated to this IO
- no documented failure mode

Paths below may work correctly most of the time — the issue is absence of governance, not presence of bugs.

---

## §2 — Inbound IO (data into Zangetsu)

### IN-01 — Binance REST ingress (OHLCV / funding / OI)
- **Path**: `data_collector.py::fetch_with_retry` → Binance API
- **Schema**: Binance-defined; not re-validated on our side
- **Rate limit**: handled by retry logic; no observability on rate-limit near-miss
- **Consumer**: `data/*/parquet` files, read by all workers
- **Gap**: no integrity attestation (was flagged as Phase 0 v2 non-goal; Phase 1 exposes it as Layer-3 gap)
- **Failure mode**: upstream outage / rate-limit → stale parquet; workers silently use latest slice
- **Severity (per drift map D-13)**: HIGH under tamper, MEDIUM under outage

### IN-02 — AKASHA memory reads
- **Path**: bot `/sync` + miniapp `/api/akasha/context` + session boot
- **Schema**: `{chunks: [...]}` loose JSON
- **Rate limit**: none client-side
- **Consumer**: many (Mac bot + miniapp + r2_n4 + Calcifer notifier)
- **Gap**: no schema version; chunk ordering / relevance undefined on consumer side
- **Failure mode**: AKASHA down → bot continues without context (graceful), miniapp shows empty result
- **Severity**: MEDIUM

### IN-03 — Telegram inbound (messages + callback_query)
- **Path**: bot long-poll `/getUpdates`
- **Schema**: Telegram-defined; parsed in agent_v2.py
- **Rate limit**: 30s long-poll timeout; Telegram imposes own limits
- **Consumer**: bot `_msg_queue`
- **Gap**: `_msg_queue` is unbounded (Explore agent flagged earlier)
- **Failure mode**: queue growth under Claude CLI timeout bursts
- **Severity**: MEDIUM

### IN-04 — Redis consumer group (Nexus subtasks)
- **Path**: `agent_v2.py::redis_worker` → redis stream `stream:subtask:executor`
- **Schema**: JSON with `instruction` + `timeout_sec`
- **Rate limit**: none client-side
- **Consumer**: runs `codex -p` with subprocess
- **Gap**: no schema version; no dead-letter handling
- **Failure mode**: malformed message → worker retry or silent drop
- **Severity**: LOW (optional, disabled by default)

### IN-05 — Claude Inbox read (for CLI ingest)
- **Path**: `:8765/api/submit` (miniapp upload consumer + direct)
- **Schema**: defined in the Inbox service
- **Rate limit**: none observed
- **Consumer**: Claude CLI pulls from Inbox (backchannel)
- **Gap**: no integration contract between Inbox and Claude CLI
- **Severity**: LOW

---

## §3 — Outbound IO (Zangetsu writing externally)

### OUT-01 — Telegram (via calcifer/notifier.py)
- **Path**: `notify_telegram(agent_name, finding)` → `api.telegram.org/bot.../sendMessage`
- **Consumers**: anyone who calls `process_finding` — Calcifer, Markl, R2-N4 watchdog, future Phase 6 alerts
- **Gap**: no rate limit (F17 in mutation_blocklist v2 addresses but not yet enforced); severity-only filter; no deduplication (same finding can be sent multiple times by different agents)
- **Failure mode**: Telegram API error → `notify_telegram` returns False silently; finding is lost if only Telegram was the channel
- **Severity**: MEDIUM → HIGH once Phase 6 adds more alert sources

### OUT-02 — AKASHA POST /memory
- **Path**: `notifier.py::write_to_akasha_sync` POST to `AKASHA_URL/memory`
- **Consumers**: same as OUT-01
- **Gap**: no schema version enforced by AKASHA; no dedup; no audit of "who wrote what"
- **Failure mode**: network error → silent (try/except pass)
- **Severity**: MEDIUM

### OUT-03 — AKASHA POST /compact
- **Path**: any operator CLI that triggers compact
- **Consumers**: operator (typically j13 or Claude CLI session cleanup)
- **Gap**: ungated (Phase 0 v2 EXT-003 / BL-F-020 / BL-R-013 flagged)
- **Failure mode**: chunk deletion — irreversible
- **Severity**: **GLOBAL** (highest on this list)

### OUT-04 — GitHub push
- **Path**: `git push origin main` from Alaya / Mac
- **Consumers**: GitHub remote + any CI / downstream
- **Gap**: pre-commit hooks enforce some rules; pre-receive hooks partially enforce §17.3 / §17.5 / §17.7 but evidence is not centralized
- **Failure mode**: force-push or bypass via `--no-verify` → uncaught
- **Severity**: HIGH (hard to detect post-hoc)

### OUT-05 — Claude Inbox POST /api/submit
- **Path**: miniapp `/api/upload` → Claude Inbox `:8765/api/submit`
- **Consumers**: miniapp users (mostly j13)
- **Gap**: no content validation beyond size limit; auth is miniapp initData only
- **Failure mode**: Inbox reject → UI shows error to user; benign
- **Severity**: LOW

### OUT-06 — Binance order API (FUTURE, not yet)
- NOT YET present in Zangetsu. But when deployable alphas reach "LIVE" they are expected to actually trade. The path doesn't exist yet.
- **Gap**: designing it now would be premature (Phase D5 / Phase 7 down the line); flagged so ops review catches it before accidental introduction.

---

## §4 — Cross-process IO (same host)

### XP-01 — `/tmp/zangetsu_live.json` file
- **Writer**: `scripts/zangetsu_snapshot.sh` every 1 min
- **Readers**: `d-mail-miniapp/server.py::zangetsu_live` endpoint; r2_n4_watchdog (implicit: none in code but logical possibility); possibly downstream user scripts
- **Schema**: `{ts, version_log_top, epoch, archive_count, workers, tiers, strategies, v10_db, v10_last_1h, orphan_processing, recent_bad_errors, disk_pct, log_mb, a2_stats_latest}` — observed but not declared
- **Gap**: no stale-freshness alert; no schema version; no atomic-write guarantee documented
- **Failure mode**: cron fails → readers see stale data silently
- **Severity**: MEDIUM (Phase 6 adds freshness monitor)

### XP-02 — `/tmp/j13-current-task.md` file
- **Writer**: Mac Claude CLI `Stop` hook `update-current-task.sh` → rsync / scp to Alaya (not yet confirmed)
- **Readers**: miniapp `/api/current-task`
- **Schema**: free-form markdown + size limit
- **Gap**: cross-host sync mechanism is uncatalogued; bidirectional conflict undefined
- **Severity**: LOW (content is advisory)

### XP-03 — `/tmp/calcifer_deploy_block.json` file
- **Writer**: Calcifer supervisor.py
- **Readers**: Claude CLI hooks, R2-N4 watchdog, CI hooks, future version-bump gate
- **Schema**: `{status, deployable_count, last_live_at_age_h, ts, iso, reason}`
- **Gap**: BL-F-021 TOCTOU (already documented in Phase 0 v2)
- **Severity**: HIGH (addressed in Phase 0 v2 blocklist)

### XP-04 — `config/a13_guidance.json` + `config/a13_gating.json`
- **Writer**: `services/arena13_feedback.py` every 5 min
- **Readers**: A1 worker at periodic intervals
- **Schema**: defined in arena13_feedback (not versioned)
- **Gap**: no observer for "guidance changed drastically"; soft cap `MAX_WEIGHT_DELTA_PCT=50%` is the only guard
- **Severity**: MEDIUM

### XP-05 — `engine.jsonl` unified log
- **Writer**: all A1/A23/A45 workers stdout merged
- **Readers**: `r2_n4_watchdog` regex parser, hourly report scripts, human debug
- **Gap**: no schema contract; log rotation unspecified; parsers are regex-based and fragile
- **Severity**: MEDIUM

### XP-06 — Redis keys
- **Writers/Readers**: miniapp + Mac bot + Calcifer + agent_v2 session_store
- **Key schema**:
  - `session:macmini13bot:{thread_id}` (hash)
  - `activity:macmini13bot:{thread_id}` (hash)
  - `output:macmini13bot:{thread_id}:history` (list)
  - `shorthand:dict:v1` (hash)
  - `TASK_QUEUE_ZSET` (zset)
  - `TASK_STATUS_PREFIX:<id>:status` (string, 24h TTL)
  - `job:{job_id}` (string, 24h TTL)
  - `heartbeat:{REDIS_GROUP}:{REDIS_CONSUMER}` (hash with 120s TTL)
- **Gap**: key naming is documented only in code + notifier module; no central registry
- **Severity**: LOW (docker-isolated, Tailscale-only access)

---

## §5 — Cross-host IO (Mac ↔ Alaya)

### XH-01 — Mac Claude CLI hook → Alaya sync
- **Path**: likely `rsync` or `scp` invoked by `update-current-task.sh` Stop hook; needs verification
- **Payload**: `/tmp/j13-current-task.md` content
- **Gap**: sync mechanism not documented; failure mode = stale current-task on Alaya; miniapp shows old data
- **Severity**: LOW

### XH-02 — Mac Codex / Gemini CLI → Alaya
- **Path**: SSH from Mac to Alaya for executions (seen today multiple times)
- **Payload**: arbitrary commands (read + write)
- **Gap**: per-command audit only via SSH session log; no standardized "agent-action → Alaya" audit lineage
- **Severity**: HIGH if agent goes off-the-rails (see BL-F-019)

### XH-03 — Mac bot `/home/j13/dev/d-mail/agent_v2.py` → Alaya AKASHA
- **Path**: HTTP over Tailscale → AKASHA `:8769`
- **Payload**: session summaries, memory chunks
- **Gap**: no per-agent ACL (any caller with the URL + POST can write)
- **Severity**: MEDIUM

### XH-04 — Miniapp Alaya hosting + Caddy
- **Path**: Caddy `:443` → localhost `:8771`
- **Auth**: initData HMAC
- **Gap**: Caddy config lives only on Alaya (`/etc/caddy/Caddyfile`); not in git
- **Severity**: MEDIUM (deploy drift)

### XH-05 — Data-collector cron → Alaya parquet
- **Path**: Alaya cron pulls from Binance directly (no Mac involved)
- **Gap**: data integrity per IN-01
- **Severity**: HIGH (data ingress is uncontrolled; if Binance API compromised or MITM'd over open internet, no attestation)

---

## §6 — Control-surface IO (how commands reach Zangetsu)

### CS-01 — SSH into Alaya
- **Path**: `ssh j13@100.123.49.102`
- **Commands**: anything
- **Gap**: per-command audit = shell history only
- **Severity**: HIGH (broadest control surface)

### CS-02 — @macmini13bot Telegram commands
- **Path**: Telegram → bot → Claude CLI → Alaya (when needed)
- **Commands**: free-text or slash commands
- **Gap**: destructive /confirm flow is good; non-destructive commands have no explicit audit beyond engine.jsonl via Claude CLI
- **Severity**: MEDIUM

### CS-03 — d-mail miniapp (v0.5.5)
- **Path**: Caddy → miniapp `:8771`
- **Commands**: 20 endpoints (catalogued in team-meeting findings)
- **Gap**: audit via `audit()` function is excellent; but no external retention policy for audit log
- **Severity**: LOW

### CS-04 — calcifer miniapp (:8772)
- **Path**: similar
- **Commands**: separate set; out of this Zangetsu scope but shares Telegram + auth infra
- **Severity**: LOW (scope-adjacent)

### CS-05 — direct DB access via docker exec
- **Path**: anyone with Alaya SSH + docker group access can `docker exec deploy-postgres-1 psql`
- **Commands**: any SQL
- **Gap**: DKR-001 in Phase 0 v2 (BL-F-019 covers it). Gemini Phase 1 §E.2 elevates this: renders L8.G Governance UNENFORCEABLE — no code-level gate can block what runs inside the container.
- **Severity**: **BLOCKER (upgraded v2 from HIGHEST)** — treat with BLOCKER discipline equal to D-01 Control Plane gap. Phase 2 BLOCKER-list = {D-01, CS-05}.

### CS-06 — crontab -e on Alaya
- **Path**: `crontab -e` (operator)
- **Commands**: schedule anything
- **Gap**: cron truth lives outside git; no code review of cron changes
- **Severity**: HIGH

### CS-07 — Shell history as de facto mutation log (added v2 per Gemini §E.1)
- **Path**: `~/.bash_history` / `~/.zsh_history` on Mac + Alaya; `~/.claude/hooks/audit.log` on Mac
- **Commands**: any interactive / SSH-session command typed by operator
- **Gap**: shell history is local, rotates, has no durable retention policy. The pre-bash hook `audit.log` is more durable but not consulted by any monitoring
- **Severity**: HIGH — this is the **primary bypass of CS-01** audit visibility

### CS-08 — systemd journal as event log (added v2 per Gemini §E.1)
- **Path**: `journalctl` on Alaya
- **Commands**: records start/stop/restart of systemd-managed services (console-api, dashboard-api)
- **Gap**: Zangetsu workers are lockfile-managed not systemd, so workers don't appear here. But d-mail-miniapp + calcifer-supervisor are systemd (per Phase 0 team-meeting findings). Journal retention is OS-default, not policy-controlled
- **Severity**: MEDIUM — useful signal, poorly integrated into Zangetsu observability

### XP-07 — `/tmp/*.md` hourly report consumption (added v2 per Gemini §E.1)
- **Writers**: cron scripts `signal_quality_report.py`, `v10_alpha_ic_analysis.py`, `v10_factor_zoo_report.py`, `v8_vs_v9_metrics.py` writing `/tmp/v9_*.md`, `/tmp/v10_*.md`
- **Readers**: unmapped in repo; may be read by miniapp, Telegram bot, or human operator via tail
- **Gap**: report files are written but consumption path not documented — a hidden cross-process dependency
- **Severity**: MEDIUM

---

## §7 — Roll-up (v2 post-Gemini)

| Direction | Total | Severity distribution |
|---|---:|---|
| Inbound | 5 | HIGH 1, MEDIUM 3, LOW 1 |
| Outbound | 5 (+ future 1) | HIGH 2, MEDIUM 2, LOW 1, GLOBAL 1 |
| Cross-process | **7** (+XP-07 reports) | HIGH 1, MEDIUM 4, LOW 2 |
| Cross-host | 5 | HIGH 2, MEDIUM 2, LOW 1 |
| Control surface | **8** (+CS-07 shell history, +CS-08 systemd journal) | BLOCKER 1, HIGH 3, MEDIUM 3, LOW 1 |

**Total IO paths = 30**. **Uncontrolled or loosely-controlled: 30**. (Everything here qualifies as "not centrally governed" by definition of this doc.)

**Added v2**: +3 paths (CS-07, CS-08, XP-07). CS-05 reclassified HIGHEST → BLOCKER.

---

## §8 — Priority for Phase 2 / Phase 6

| IO | Why priority |
|---|---|
| CS-05 docker exec | bypasses all code gates — highest blast radius |
| IN-01 / XH-05 Binance ingress | data integrity; affects truth integrity of the whole pipeline |
| OUT-03 AKASHA /compact | irreversible chunk deletion |
| CS-01 SSH access | broadest surface; needs audit lineage |
| OUT-01 Telegram + OUT-02 AKASHA /memory | spam / retry bomb vector (F16 / F17) |
| XP-03 TOCTOU block file | already in blocklist; Phase 7 nonce fix |

These go into Phase 2 control-plane + Phase 6 observability design.

---

## §9 — Confidence

- **VERIFIED**: path existence, writer / reader identities, gap descriptions
- **PROBABLE**: severity scoring (biased toward worst case; Gemini adversarial may downgrade some)
- **INCONCLUSIVE**: XH-01 Mac → Alaya sync mechanism (needs explicit trace)
- **DISPROVEN**: "Zangetsu workers make outbound POST/PUT/DELETE" — correctly shown as zero in Phase 0 (only wrapped intermediaries write outward)

---

## §10 — Non-goals

- Not designing the control plane here — Phase 2.
- Not implementing monitors — Phase 6.
- Not claiming any path is wrong — just unmonitored.
