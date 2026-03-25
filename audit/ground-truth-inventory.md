# Ground Truth Inventory — 2026-03-21

> RESEARCH ONLY. Ground-truth as observed. No assumptions.
> Data collected via direct SSH + docker + psql queries.

---

## I. GitHub Repositories (7 total — NOT 28)

| Repo | Language | Last Updated | Visibility | Notes |
|------|----------|-------------|------------|-------|
| M116cj/j13-ops | HTML | 2026-03-18 | public | Infrastructure ops, runbooks, install scripts |
| M116cj/qbeyer-models | — | 2026-03-17 | public | No primary language detected (data/configs) |
| M116cj/winiswin2 | Python | 2026-03-10 | public | Unknown purpose |
| M116cj/everychance_i_get | Python | 2026-03-08 | public | Unknown purpose |
| M116cj/winiswin | Python | 2026-03-08 | public | Unknown purpose |
| M116cj/CodeSnippets | CSS | 2026-03-08 | public | Unknown purpose |
| M116cj/quant-trading | Python | 2026-03-08 | public | Likely zangetsu origin or research |

**Critical finding**: zangetsu source code is NOT on GitHub. deploy-trader-1 was built from source at ~/projects/ (now deleted). Docker image exists; source does not.

---

## II. Local-Only Services (Mac, not on GitHub)

| Service | Runtime | Purpose | Status |
|---------|---------|---------|--------|
| d-mail | launchd + Claude Code CLI | Telegram → Claude Code bridge | Active |
| gemini-bot | Python/launchd | @Geminialayabot, calls `gemini` CLI subprocess | Active |

---

## III. Alaya Docker Containers (15 running)

### zangetsu stack (deploy_zangetsu_net)

| Container | Image | Uptime | Health | Purpose |
|-----------|-------|--------|--------|---------|
| deploy-postgres-1 | pgvector/pgvector:pg15 | 44h | healthy | Primary DB: 22 tables, 52 execution_log rows |
| deploy-redis-1 | redis:7-alpine | 44h | healthy | **UNUSED** — zero Redis imports in zangetsu code |
| deploy-trader-1 | deploy-trader (local image) | 23h | healthy | Trading execution via ccxt (Binance paper) |
| deploy-ml_core-1 | deploy-ml_core (local image) | 21h | healthy | LightGBM training (CPU-only, no GPU) |
| deploy-dashboard-1 | deploy-dashboard (local image) | 44h | healthy | Trading dashboard, port 8080 (0.0.0.0 EXPOSED) |
| echelon | echelon-echelon (local image) | 6m | healthy | PostgreSQL → Telegram signal relay (BROKEN: thread delivery) |

### magi stack (magi_default)

| Container | Image | Uptime | Health | Purpose |
|-----------|-------|--------|--------|---------|
| magi-litellm-1 | ghcr.io/berriai/litellm:main-latest | 18h | — | LLM proxy, port 4000 (0.0.0.0 EXPOSED — SECURITY RISK) |
| magi-redis-1 | redis:7-alpine | 44h | — | LiteLLM session cache |

### observability stack (obs)

| Container | Image | Uptime | Purpose |
|-----------|-------|--------|---------|
| obs-prometheus | prom/prometheus:v3.2.1 | 17m | Metrics scraper (127.0.0.1:9090) |
| obs-grafana | grafana/grafana:11.5.2 | 18m | Dashboards (127.0.0.1:3000) |
| obs-loki | grafana/loki:3.4.2 | 18m | Log aggregation (127.0.0.1:3100) |
| obs-promtail | grafana/promtail:3.4.2 | 18m | Log collection agent |
| obs-cadvisor | gcr.io/cadvisor/cadvisor:v0.52.0 | 18m | Container metrics |
| obs-node-exporter | prom/node-exporter:v1.9.0 | 18m | Host OS metrics |

### management

| Container | Image | Uptime | Purpose |
|-----------|-------|--------|---------|
| portainer | portainer/portainer-ce:latest | 44h | Docker UI, port 9000 (0.0.0.0 EXPOSED — CRITICAL) |

---

## IV. Alaya Systemd Services

| Service | Status | Since | Memory | Purpose |
|---------|--------|-------|--------|---------|
| local-llm.service | ACTIVE | 2026-03-20 00:23 | 1.0G | llama-server, Qwen2.5-Coder-14B-Q4_K_M.gguf, port 8001 (127.0.0.1) |
| local-queue.service | ACTIVE | 2026-03-20 05:11 | 1.8M | inotifywait queue daemon for Qwen requests |
| dashboard.service | ACTIVE | 2026-03-19 07:39 | 45.7M | Python, 432 LOC, FastAPI, port 8080 |
| miniapp.service | ACTIVE | 2026-03-19 04:38 | 44.5M | Python, 65 LOC, FastAPI, port 7700 — BROKEN |
| network-watchdog.service | ACTIVE | — | — | Network connectivity watchdog |
| **alaya-agent.service** | **INACTIVE (dead)** | died 2026-03-20 16:14 | — | Planner+Executor bot, 1057 LOC — stopped ~10h ago |
| amadeus.service | INACTIVE (disabled) | — | — | ORPHAN — unit file exists, source missing |
| king-crimson.service | INACTIVE (disabled) | — | — | ORPHAN — unit file exists, source missing |
| r-steiner.service | INACTIVE (disabled) | — | — | ORPHAN — unit file exists, source missing |
| dcbot.service | INACTIVE (disabled) | — | — | ORPHAN — unit file exists, source missing |

---

## V. PostgreSQL Database (deploy-postgres-1)

**DB**: zangetsu | **Driver**: pgvector/pg15 | **Network**: deploy_zangetsu_net

| Table | Rows | Status | Purpose |
|-------|------|--------|---------|
| execution_log | 52 (27 BUY / 25 SELL) | active | Trade signals; last entry 2026-03-21 02:11 UTC |
| **ohlcv_1m** | **0** | **EMPTY** | Market data — never populated |
| echelon_state | 1 | active | echelon high-water mark (last_seen_id=51) |
| champions | — | active | Model tournament winners |
| pool_champions | — | active | Pool-level champions |
| meta_rankings / pool_meta_rankings | — | active | Meta-ranking across champions |
| meta_tournaments / pool_meta_tournaments | — | active | Tournament run metadata |
| tournament_runs | — | active | Individual tournament records |
| validation_audit / validation_gates / valkyrie_audit | — | active | valkyrie validation results |
| live_elo | — | active | ELO ratings for live trading |
| regime_vectors | — | active | Market regime feature vectors |
| market_context | — | active | Market context snapshots |
| circuit_breaker_log | — | active | Circuit breaker events |
| data_quality_reports / data_summary | — | active | Data quality and aggregation |
| tier_heartbeats / system_metrics | — | active | System health records |
| meta_champion_audit | — | active | Champion selection audit |

---

## VI. On-Disk Code Inventory (Alaya)

| Path | Language | LOC | Status |
|------|----------|-----|--------|
| ~/agent/agent.py | Python | 876 | Present, service DEAD |
| ~/agent/bot.py | Python | 181 | Present, service DEAD |
| ~/grok-bot/bot.py + grok_bot.py | Python | 456 | Running (via what mechanism?) |
| ~/dashboard/main.py | Python | 432 | Running as systemd service |
| ~/miniapp/main.py | Python | 65 | Running but BROKEN |
| ~/j13-ops/infra/echelon/echelon.py | Python | ~190 | Running in Docker |
| ~/j13-ops/infra/observability/ | YAML | — | Running (5 services) |
| ~/j13-ops/infra/gpu-coordinator.sh | Bash | ~80 | Present, not yet invoked |
| ~/j13-ops/audit/blockers.md | — | — | 7+ blockers documented |

**zangetsu source**: NOT on disk. Only inside Docker images.

---

## VII. System Resources (Alaya, as of 2026-03-21)

| Resource | Used | Total | % | Notes |
|----------|------|-------|---|-------|
| Disk (/) | 52G | 915G | 6% | Fine |
| RAM | 7.0G | 31G | 23% | Fine |
| GPU VRAM | 10,311 MiB | ~12,288 MiB | 84% | Qwen consuming 10.3GB — only 1.6GB free |

---

## VIII. Network Exposure

| Port | Binding | Service | Risk Level |
|------|---------|---------|-----------|
| 4000 | **0.0.0.0** | LiteLLM proxy (master_key known) | CRITICAL |
| 8080 | **0.0.0.0** | zangetsu dashboard | HIGH |
| 9000 | **0.0.0.0** | Portainer (full Docker control) | CRITICAL |
| 7700 | 0.0.0.0 | miniapp FastAPI (broken) | MEDIUM |
| 8001 | 127.0.0.1 | Qwen llama-server | safe |
| 9090 | 127.0.0.1 | Prometheus | safe |
| 3000 | 127.0.0.1 | Grafana | safe |
| 3100 | 127.0.0.1 | Loki | safe |

---

## IX. Known Issues

| ID | Severity | Issue | Impact |
|----|----------|-------|--------|
| I1 | CRITICAL | Portainer port 9000 internet-exposed | Full Docker control accessible |
| I2 | CRITICAL | LiteLLM port 4000 internet-exposed | LLM proxy with known master key |
| I3 | HIGH | zangetsu source not version-controlled | Source code lost if images cleared |
| I4 | HIGH | alaya-agent.service dead since 2026-03-20 | AI assistant offline 10h+ |
| I5 | HIGH | echelon Telegram thread delivery broken | All signal notifications failing |
| I6 | HIGH | ohlcv_1m table permanently empty | Market data not stored |
| I7 | MEDIUM | miniapp queries non-existent `strategies` table | FastAPI 500 on every request |
| I8 | MEDIUM | deploy-redis-1 completely unused | Wastes RAM, Redis URL set but unused |
| I9 | MEDIUM | 4 orphan systemd unit files | amadeus, king-crimson, r-steiner, dcbot |
| I10 | MEDIUM | ~/projects/ directory missing | Docker build context lost |
| I11 | LOW | LightGBM CPU-only | GPU available but unused for training |
| I12 | LOW | PAT read-only | Cannot create repos or push |

---

## X. Claim vs Reality

| Claimed | Reality |
|---------|---------|
| 28 repositories | 9 total (7 GitHub + 2 local) |
| Full trading pipeline | Paper trade only; ohlcv_1m empty |
| GPU-accelerated trading | LightGBM CPU-only; GPU = Qwen only |
| Redis as message bus | Redis running, zero code usage |
| valkyrie = HFT execution engine | valkyrie.py = statistical validation (Monte Carlo + CPCV) |
| echelon = working signal relay | Running; Telegram delivery broken |
| All services healthy | agent dead, miniapp broken, 4 orphan units |

---

*Collected: 2026-03-21 via SSH direct query (docker ps, psql, systemctl, ss, nvidia-smi).*
