# Gap Analysis — j13 Alaya Stack 2026-03-21

> Cross-reference: ground-truth-inventory.md (what we have) vs tech-landscape-2026.md (what is best available).
> Sorted by priority: revenue-blocking first, then stability, then nice-to-have.

---

## 4A. Per-Repo Technology Layer Analysis

### zangetsu (deploy-trader-1, deploy-ml_core-1, deploy-dashboard-1)

Source code is inside Docker images only — no on-disk files, no GitHub repo.

| Layer | Current | Recommended | Migration Difficulty | Notes |
|-------|---------|-------------|---------------------|-------|
| Version control | **NONE** (images only) | GitHub repo | **BLOCKED** — need to extract source from image first | Critical risk |
| Time-series DB | PostgreSQL ohlcv_1m (empty) | QuestDB for OHLCV hot path | hard | ohlcv_1m never populated; need data pipeline first |
| Message bus | Redis (REDIS_URL set, unused) | Redis Streams for signal fanout | trivial | Library already running; add xadd/xread calls |
| Feature store | PostgreSQL ad-hoc tables | PostgreSQL (offline) + Redis hash (online) | trivial | Schema already exists; just add Redis hash writes |
| Package manager | unknown (inside image) | uv | moderate | Rebuild Dockerfiles with uv |
| Python version | unknown (inside image) | 3.12 | moderate | Rebuild base images |
| DataFrame | Pandas (assumed) | Pandas 2.x | trivial | Pin version in requirements |
| GPU training | CPU-only LightGBM | CPU-only (correct for LightGBM) | N/A — correct as-is | GPU reserved for inference |
| Observability | none (no OTel) | Prometheus metrics endpoint | moderate | Add prometheus-client to containers |

**Key gap**: zangetsu source is not version-controlled. Every other improvement is blocked until source is extractable and on GitHub.

---

### alaya-agent (~/agent/)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Service status | DEAD (stopped 2026-03-20 16:14) | Running + monitored | trivial — just start it |
| Runtime | asyncio | uvloop | trivial |
| Package manager | requirements.txt (pinned) | uv | trivial |
| Retry/resilience | unknown | httpx retry + circuit breaker | moderate |
| Observability | none | Prometheus counter for commands | moderate |

---

### echelon (~/j13-ops/infra/echelon/)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Telegram delivery | BROKEN (thread 400) | Fixed send_telegram with fallback | **trivial — SCP fixed file + rebuild** |
| Signal transport | PostgreSQL polling (15s) | Redis Streams push | moderate |
| Exactly-once | no (high-water mark) | Redis SETNX dedup | moderate |
| Python version | unknown | 3.12 | moderate |
| Package manager | requirements.txt | uv | trivial |

---

### grok-bot (~/grok-bot/)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Runtime | asyncio | uvloop | trivial |
| Tests | 9 smoke tests (passing) | add integration test | moderate |
| Deployment | unknown mechanism | systemd service (like agent) | moderate |
| Package manager | requirements.txt (pinned) | uv | trivial |

---

### miniapp (~/miniapp/)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Database schema | queries Railway `strategies` table (MISSING) | query actual zangetsu tables | **trivial — 65 LOC, rewrite API** |
| Exposure | 0.0.0.0:7700 | reverse proxy or auth | moderate |
| Python | systemd, raw | uv venv | trivial |

---

### dashboard (~/dashboard/)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Exposure | 0.0.0.0:8080 | firewall or auth layer | moderate |
| Runtime | asyncio | uvloop | trivial |
| Source control | on-disk only | GitHub | moderate |

---

### magi (LiteLLM proxy)

| Layer | Current | Recommended | Migration Difficulty |
|-------|---------|-------------|---------------------|
| Network exposure | 0.0.0.0:4000 | localhost or Tailscale-only | **trivial — change port binding** |
| Master key | sk-alaya-litellm-2026 (known) | rotate key | trivial |
| Source backup | config recovered to j13-ops | version-control config | trivial |
| Redis | magi-redis-1 present | keep (session cache) | N/A |

---

## 4B. Alaya Infrastructure

### Services to ADD

| Service | Why | Priority | Estimated Hours |
|---------|-----|----------|----------------|
| Firewall (ufw) | Block 4000, 8080, 9000 from internet; allow Tailscale | CRITICAL | 0.5h |
| fail2ban | SSH brute-force protection | HIGH | 1h (needs sudo) |
| QuestDB | OHLCV hot-path time-series | MEDIUM | 2h setup + 4h zangetsu integration |
| Redis Streams consumer (echelon) | Replace polling with push-based signal delivery | MEDIUM | 3h |

### Services to REMOVE or REPLACE

| Service | Action | Reason | Priority |
|---------|--------|--------|----------|
| deploy-redis-1 | REMOVE after activating Redis Streams | Zero usage, wastes 200MB RAM | MEDIUM |
| 4 orphan systemd units | REMOVE (sudo required) | amadeus, king-crimson, r-steiner, dcbot — pollute systemd | LOW |
| alaya-agent.service | RESTART + add watchdog | Currently dead | HIGH |

### Optimal Resource Allocation (RTX 3080 10GB, 32GB RAM)

| Workload | VRAM | RAM | CPU | Notes |
|----------|------|-----|-----|-------|
| Qwen2.5-Coder-14B (inference) | **10.3GB** | 1GB | 8 threads | Running 24/7; leaves only 1.6GB free |
| LightGBM training | 0MB (CPU) | 2-4GB | all cores | CPU-only; no VRAM conflict |
| Docker containers (zangetsu) | 0MB | ~1GB total | minimal | Mostly idle between trades |
| Observability stack | 0MB | ~500MB | minimal | LGTM-lite |
| OS + other | 0MB | ~500MB | — | — |

**Current VRAM state**: Qwen holds 10.3GB of 12GB. Only 1.6GB free. LightGBM training has zero VRAM conflict (CPU-only confirmed). GPU coordinator script exists but is not needed for LightGBM.

**If GPU training needed later** (e.g., LSTM, XGBoost with GPU): gpu-coordinator.sh is ready — SIGTERMs llama-server, waits for VRAM free, runs training, lets systemd restart Qwen.

**GPU time-sharing strategy (current recommendation)**: No sharing needed. Qwen uses GPU 24/7 for inference; LightGBM uses CPU. This is the correct allocation.

### Should any workloads move to local Mac?

| Workload | Move to Mac? | Reason |
|----------|-------------|--------|
| gemini-bot | already on Mac | correct |
| d-mail | already on Mac | correct |
| LightGBM training | no — keep on alaya | CPU-bound but benefits from alaya's 32GB RAM |
| Dashboard | no — keep on alaya | needs DB access |
| Model experimentation | yes — Mac M-series is excellent for CPU ML | fast iteration |

---

## 4C. Trading Pipeline — Critical Path to First Revenue

**Current state**: paper trading BTC/USDT on Binance. 52 signals generated (27 BUY / 25 SELL). ohlcv_1m empty. echelon broken. valkyrie = validation framework (not live execution).

### Critical Path

```
Step 1: Fix echelon Telegram delivery [BLOCKED: fixed locally, needs SCP + rebuild]
  └── Unblocks: j13 can see signals in real-time

Step 2: Verify zangetsu signals are valid [BLOCKED: need to inspect execution_log quality]
  └── Requires: source code visibility (extract from Docker image)

Step 3: Populate ohlcv_1m [BLOCKED: data ingestion pipeline missing]
  └── Without OHLCV data, ml_core has nothing to train on

Step 4: Run valkyrie validation on paper-trade results [CAN DO NOW]
  └── 52 signal sample is small but validation can begin

Step 5: Fix miniapp to display real zangetsu data [TRIVIAL: 65 LOC rewrite]
  └── Unblocks: monitoring dashboard for j13

Step 6: Version-control zangetsu source [BLOCKED: need sudo or Docker image extraction]
  └── Until done: any container restart could lose all improvements

Step 7: Live trading (real money) [BLOCKED: steps 1-6 incomplete]
  └── Hard dependency: valkyrie must PASS, OHLCV pipeline must work, signals must be visible
```

### What Can Be Parallelized

| Task | Depends On | Can Run In Parallel With |
|------|-----------|--------------------------|
| Fix echelon | nothing | miniapp fix, firewall |
| miniapp fix | nothing | echelon fix, firewall |
| firewall setup | sudo access | echelon fix, miniapp fix |
| Restart alaya-agent | nothing | all of the above |
| OHLCV pipeline | zangetsu source visibility | firewall setup |
| valkyrie validation | execution_log (52 rows available) | all of the above |

### Hard Sequential Dependencies

1. Source code visibility → OHLCV pipeline → ml_core training with real data → better champions
2. Firewall → security posture → live trading with real money
3. valkyrie PASS → live trading (regulatory/risk gate)

---

## 4D. Gap Analysis Master Table

> Sorted by priority: revenue-blocking → stability → nice-to-have.

| Repo/Service | Current State | Target State | Migration Difficulty | Est. Hours | Depends On | Risk |
|-------------|--------------|--------------|---------------------|-----------|------------|------|
| **echelon** | Telegram delivery BROKEN | signals arrive in Telegram | **trivial** | 0.5h | nothing | HIGH — signal visibility |
| **alaya-agent** | DEAD since 2026-03-20 | Running + monitored | trivial | 0.25h | nothing | HIGH — AI assistant offline |
| **Firewall (ufw)** | none — 3 ports exposed | ports 4000/8080/9000 blocked | trivial | 0.5h | sudo | CRITICAL — security |
| **LiteLLM key rotation** | known master key | rotated + localhost-only | trivial | 0.25h | nothing | CRITICAL — billed API exposed |
| **miniapp** | queries missing `strategies` table | queries actual zangetsu tables | trivial | 1h | nothing | MEDIUM — dashboard broken |
| **zangetsu source** | Docker image only | GitHub repo + on-disk | hard | 4h | Docker image extraction | HIGH — loss risk |
| **ohlcv_1m pipeline** | EMPTY — no data | fetching + storing OHLCV | hard | 8h | zangetsu source | HIGH — training has no data |
| **valkyrie validation** | not run against paper results | pass/fail on 52-signal sample | moderate | 3h | zangetsu source | HIGH — blocks live trading |
| **fail2ban / SSH hardening** | none | installed + configured | moderate | 1h | sudo | HIGH — security |
| **alaya-agent watchdog** | none | systemd WatchdogSec= | trivial | 0.25h | nothing | MEDIUM — service restarts on crash |
| **uv migration (all projects)** | pip/requirements.txt | uv sync | trivial | 2h | nothing | LOW |
| **uvloop (bots)** | asyncio | uvloop.install() | trivial | 0.5h | nothing | LOW |
| **Redis Streams (echelon)** | PostgreSQL polling 15s | push-based sub-ms delivery | moderate | 3h | nothing | MEDIUM |
| **Python 3.12 base images** | unknown (3.10/3.11 est.) | 3.12 Dockerfiles | moderate | 4h | zangetsu source visible | LOW |
| **4 orphan systemd units** | disabled but present | removed | trivial | 0.25h | sudo | LOW — cleanup |
| **QuestDB for OHLCV** | not deployed | QuestDB container + ingest | hard | 6h | ohlcv pipeline done first | LOW — optimization |
| **SigNoz (upgrade observability)** | LGTM-lite running | full OTel traces | moderate | 4h | deferred | LOW — current stack works |
| **Prefect 3 (orchestration)** | systemd timers | managed ML pipeline | hard | 8h | deferred | LOW — not needed yet |
| **Coolify (rolling deploys)** | manual down+up | zero-downtime deploys | moderate | 2h | deferred | LOW — nice-to-have |

---

*Analysis date: 2026-03-21. Based on ground-truth-inventory.md + tech-landscape-2026.md.*
