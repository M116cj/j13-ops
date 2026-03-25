# System Dependency Map — 2026-03-21

> RESEARCH ONLY. Maps all data flows, service dependencies, and credential paths.
> Nodes = services/repos. Edges = data flow direction.

---

## I. Mermaid Architecture Diagram

```mermaid
graph TD
    subgraph MAC["Mac Mini (local)"]
        dmail["d-mail\n(launchd)\nTelegram→Claude Code bridge"]
        gembot["gemini-bot\n(launchd)\n@Geminialayabot"]
        claude["Claude Code CLI\n(claude -p subprocess)"]
        gemini_cli["gemini CLI\n(subprocess)"]
        dmail --> claude
        gembot --> gemini_cli
    end

    subgraph ALAYA["Alaya Server (100.123.49.102)"]
        subgraph ZANGETSU["deploy_zangetsu_net"]
            trader["deploy-trader-1\nccxt Binance paper\nBTC/USDT signals"]
            ml_core["deploy-ml_core-1\nLightGBM training\n(CPU-only)"]
            pg[("deploy-postgres-1\nPostgreSQL pg15+pgvector\n22 tables")]
            redis_d["deploy-redis-1\nRedis 7\n(UNUSED)"]
            dashboard_c["deploy-dashboard-1\nFastAPI dashboard\n:8080 0.0.0.0"]
            echelon["echelon\nSignal relay\n(Telegram delivery broken)"]
        end

        subgraph MAGI["magi_default"]
            litellm["magi-litellm-1\nLiteLLM proxy\n:4000 0.0.0.0 (EXPOSED)"]
            redis_m["magi-redis-1\nRedis 7\n(LiteLLM cache)"]
        end

        subgraph OBS["obs network"]
            prometheus["obs-prometheus\n:9090 (localhost)"]
            grafana["obs-grafana\n:3000 (localhost)"]
            loki["obs-loki\n:3100 (localhost)"]
            promtail["obs-promtail"]
            cadvisor["obs-cadvisor"]
            nodeexp["obs-node-exporter"]
        end

        subgraph SYSTEMD["systemd services"]
            qwen["local-llm.service\nQwen2.5-Coder-14B\nllama-server :8001"]
            queue["local-queue.service\ninotifywait queue daemon"]
            dash_svc["dashboard.service\n:8080 FastAPI\n432 LOC"]
            miniapp["miniapp.service\n:7700 FastAPI\n65 LOC — BROKEN"]
            agent["alaya-agent.service\nPlanner+Executor\n1057 LOC — DEAD"]
        end

        portainer["portainer\n:9000 0.0.0.0 (CRITICAL)"]
    end

    subgraph EXTERNAL["External APIs"]
        binance_api["Binance API\n(paper trade)"]
        tg_api["Telegram Bot API\n@Alaya13jbot"]
        tg_grok["Telegram Bot API\n@Geminialayabot / @grok"]
        anthropic_api["Anthropic API\nclaude-sonnet/opus/haiku"]
        xai_api["xAI Grok API\n(grok-4-1-fast-reasoning)"]
    end

    subgraph GITHUB["GitHub (M116cj)"]
        j13ops["j13-ops\n(HTML/YAML)"]
        quant["quant-trading\n(Python)"]
        qbeyer["qbeyer-models"]
    end

    %% zangetsu data flows
    trader -->|"BUY/SELL signals\n(execution_log)"| pg
    ml_core -->|"champion models\n(champions table)"| pg
    pg -->|"poll execution_log\nevery 15s"| echelon
    echelon -->|"formatted signal\n(BROKEN: thread 400)"| tg_api
    trader -->|"market data req"| binance_api
    binance_api -->|"OHLCV prices"| trader
    dashboard_c -->|"query DB"| pg
    pg -.->|"REDIS_URL set\nbut UNUSED"| redis_d

    %% magi flows
    litellm -->|"route requests"| anthropic_api
    litellm --> redis_m
    queue -->|"HTTP :8001"| qwen

    %% observability flows
    promtail -->|"log scrape"| loki
    cadvisor -->|"container metrics"| prometheus
    nodeexp -->|"host metrics"| prometheus
    prometheus -->|"data source"| grafana
    loki -->|"data source"| grafana

    %% Mac flows
    dmail -->|"SSH/API"| ALAYA
    tg_api -->|"webhook/poll"| dmail
    tg_grok -->|"webhook/poll"| gembot

    %% agent flows (DEAD)
    agent -.->|"DEAD\nno traffic"| tg_api
    agent -.->|"DEAD"| qwen

    %% dashboard service (systemd, not Docker)
    dash_svc -->|"query DB\n(how? no network)"| pg

    %% miniapp (BROKEN)
    miniapp -->|"asyncpg\nquery strategies\n(table missing — 500)"| pg

    %% internet exposed
    internet(["Internet"]) -->|"HTTP"| litellm
    internet -->|"HTTP"| dashboard_c
    internet -->|"HTTP"| portainer

    style redis_d fill:#ff9999,stroke:#cc0000
    style echelon fill:#ffcc99,stroke:#cc6600
    style agent fill:#ff9999,stroke:#cc0000
    style miniapp fill:#ff9999,stroke:#cc0000
    style litellm fill:#ffcc99,stroke:#cc6600
    style portainer fill:#ff6666,stroke:#cc0000
    style dashboard_c fill:#ffcc99,stroke:#cc6600
    style internet fill:#ff4444,stroke:#cc0000,color:#fff
```

---

## II. Data Flow Inventory

### Primary Signal Path (zangetsu)

```
Binance API
  → trader (ccxt, paper mode)
  → PostgreSQL execution_log (INSERT)
  → echelon (SELECT WHERE id > last_seen, every 15s)
  → Telegram Bot API (sendMessage)  ← BROKEN: thread 400
```

### Model Training Path

```
PostgreSQL (ohlcv_1m — EMPTY, regime_vectors, champions)
  → ml_core (LightGBM training, CPU-only)
  → PostgreSQL (champions table, UPDATE)
  → trader (reads champion model for signals)
```

**Note**: ohlcv_1m is empty. ml_core is running but has no market data to train on. Source of training data is unknown without inspecting container source.

### LLM Routing Path (magi)

```
Client request
  → LiteLLM proxy :4000 (internet-exposed, master_key: sk-alaya-litellm-2026)
  → Anthropic API (claude-sonnet-4-6 / claude-opus-4-6 / claude-haiku-4-5)
  → Redis cache (magi-redis-1)
```

### Local AI Path (alaya)

```
File drop to ~/.claude/scratch/queue/qwen/
  → local-queue.service (inotifywait)
  → llama-server :8001 (Qwen2.5-Coder-14B, 10.3GB VRAM)
  → response file
```

### Observability Path

```
Docker containers + host OS
  → cadvisor (container metrics) + node-exporter (host metrics)
  → Prometheus :9090 (scrape, 15s interval)
  → Grafana :3000 (visualize)

Container logs
  → promtail (scrape Docker logs)
  → Loki :3100
  → Grafana (query via LogQL)
```

---

## III. Credential / Secret Map

| Secret | Where Stored | Who Uses It | Risk |
|--------|-------------|-------------|------|
| ALAYA_BOT_TOKEN | ~/j13-ops/infra/echelon/.env | echelon | medium (server-local) |
| ALAYA_BOT_TOKEN | alaya-agent systemd env | alaya-agent | medium |
| GROK_BOT_TOKEN | grok-bot systemd/env | grok-bot | medium |
| ANTHROPIC_API_KEY | magi-litellm .env | LiteLLM → Anthropic | high (billable) |
| XAI_API_KEY | grok-bot env | grok-bot | high (billable) |
| GROUP_CHAT_ID | multiple .env files | all bots | low |
| LiteLLM master_key | litellm_config.yaml | LiteLLM proxy | HIGH (internet-exposed) |
| github_pat_* | ~/.config/gh/ on alaya | gh CLI | medium (read-only PAT) |
| POOL_DATABASE_URL | zangetsu deploy .env | all zangetsu containers | high (contains password) |
| ZANGETSU_DB_URL | miniapp env | miniapp (Railway URL) | medium (broken anyway) |
| SSH private key | ~/.ssh/ on Mac | Tailscale SSH to alaya | high |

---

## IV. Docker Network Topology

```
deploy_zangetsu_net (bridge):
  postgres:5432  ← trader, ml_core, dashboard, echelon
  redis:6379     ← trader (UNUSED)
  zangetsu containers communicate by service name

magi_default (bridge):
  litellm:4000   ← internal routing
  redis:6379     ← litellm cache

obs (bridge):
  prometheus:9090
  loki:3100
  grafana:3000
  promtail, cadvisor, node-exporter

All three networks are ISOLATED from each other.
No cross-network traffic observed.
```

---

## V. Orphaned / Dead Paths

| Path | Description | Status |
|------|-------------|--------|
| amadeus → Telegram | amadeus.service unit exists, no source | ORPHAN |
| king-crimson → ? | king-crimson.service unit exists, no source | ORPHAN |
| r-steiner → ? | r-steiner.service unit exists, no source | ORPHAN |
| dcbot → Discord | dcbot.service unit exists, no source | ORPHAN |
| alaya-agent → Telegram | 1057 LOC of Planner+Executor | DEAD (service down) |
| miniapp → Railway PostgreSQL | queries `strategies` table | BROKEN |
| trader → Redis | REDIS_URL set in env | UNUSED |
| ohlcv_1m → ml_core | market data source for training | EMPTY |

---

## VI. Inter-Service Dependencies (Startup Order)

Critical path for zangetsu stack:
1. `deploy-postgres-1` must be healthy before trader/ml_core/dashboard/echelon start
2. `deploy-trader-1` generates signals → `deploy-ml_core-1` uses same DB
3. `echelon` depends only on PostgreSQL (independent of trader uptime)
4. `deploy-dashboard-1` depends only on PostgreSQL

No hard dependency between zangetsu stack and magi stack.
Observability stack is fully independent (external network, read-only scraping).

---

*Collected: 2026-03-21 via SSH direct query.*
