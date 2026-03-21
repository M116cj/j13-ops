# Environment Snapshot — 2026-03-21

## Alaya Server

| Item | Value |
|------|-------|
| Hostname | alaya |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.8.0-106-generic |
| CPU | Intel Core i7-12700K (12th Gen, 20 threads) |
| RAM | 31 GB total, ~6.7 GB used, 24 GB available |
| Swap | 8 GB (swappiness default) |
| GPU | NVIDIA GeForce RTX 3080 12 GB VRAM |
| VRAM Used | 10.3 GB / 12 GB (86% — Qwen2.5 holds this) |
| Disk (/) | 915 GB NVMe, 50 GB used (6%) |
| Load avg | 3.28 / 3.09 / 3.03 (at scan time) |
| Uptime | 1 day 21 hours |
| Tailscale IP | 100.123.49.102 |
| Docker | 29.3.0 |
| Python | 3.12.3 |
| Node.js | 20.20.1 |
| unattended-upgrades | active ✅ |
| fail2ban | NOT installed ⚠️ |
| SSH PasswordAuth | implicit default (not explicitly disabled) ⚠️ |

## Security Gaps (Phase 1A)

1. **fail2ban not installed** — brute-force SSH attempts go unmitigated
2. **PasswordAuthentication not explicitly disabled** —  has it commented out; should be 
3. **SSH on port 22** — standard port, higher scan/attack volume

## GPU Conflict (Phase 1E)

- Qwen2.5-Coder-14B holds 10.3 GB of 12 GB VRAM
- ML training jobs inside deploy-ml_core-1 may attempt GPU access
- Current state: deploy-ml_core-1 runs without explicit GPU device mount → likely CPU-only for training
- Risk: If ML training is moved to GPU, OOM will crash Qwen

## Running Service Summary

### systemd (active)
- local-llm (Qwen2.5-Coder-14B, port 8001)
- local-queue
- alaya-bot (@Alaya13jbot)
- grok-bot (@Alaya_grokbot)
- dashboard (Command Center)
- miniapp (Zangetsu Mini App)
- network-watchdog

### Docker (healthy)
- deploy-trader-1 (zangetsu paper trader)
- deploy-ml_core-1 (zangetsu ML core)
- deploy-postgres-1 (PostgreSQL 15 + pgvector, port 5432)
- deploy-redis-1 (Redis 7, docker internal port 6379)
- deploy-dashboard-1 (port 8080)
- magi-litellm-1 (LiteLLM proxy, port 4000)
- magi-redis-1 (Redis 7, localhost:6379)
- portainer (port 9000)

## Connectivity

- Tailscale VPN: active, IP 100.123.49.102
- SSH: key-only (authorized_keys present)
- External internet: yes (Binance WebSocket active via trader)

## Local Mac

| Item | Value |
|------|-------|
| OS | macOS Darwin 25.2.0 |
| Shell | zsh |
| Claude | claude-sonnet-4-6 |
| GitHub | M116cj (PAT: fine-grained, limited scope) |
| SSH key | ~/.ssh/id_ed25519_alaya → alaya |

## Known Blockers

| ID | Blocker | Impact |
|----|---------|--------|
| B1 | PAT lacks createRepository scope | Cannot create new GitHub repos autonomously |
| B2 | M116cj/zangetsu repo: Not Found via API | Cannot read/push zangetsu source from outside containers |
| B3 | ~/projects/ directory missing | No source on disk for docker projects |
