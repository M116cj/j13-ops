# Repo & Service Status — 2026-03-21

Audit by: Claude Sonnet 4.6 (autonomous Phase 0 scan)

## Summary

Claimed "28 repos" does not match reality. Actual: 7 GitHub repos + 8 project specs (P1-P8 in /projects/) + running services.

---

## GitHub Repos

| Repo | Status | Last Push | Notes |
|------|--------|-----------|-------|
| M116cj/j13-ops | PRODUCTION | 2026-03-18 | Ops hub, server setup, project specs |
| M116cj/qbeyer-models | PRODUCTION | 2026-03-17 | LLM model releases |
| M116cj/zangetsu | SCAFFOLD? | unknown | Private? github_sync.py references it; API returns Not Found |
| M116cj/winiswin2 | DEAD | 2025-11-25 | Archived |
| M116cj/everychance_i_get | DEAD | 2025-11-02 | Archived |
| M116cj/winiswin | DEAD | 2025-10-25 | Archived |
| M116cj/CodeSnippets | DEAD | 2022-05-01 | Archived |
| M116cj/quant-trading | DEAD | 2022-02-01 | Archived |

---

## Running Services (Alaya systemd)

| Service | Status | Port | Notes |
|---------|--------|------|-------|
| alaya-bot | PRODUCTION ✅ | — | Telegram @Alaya13jbot + Qwen2.5 interface |
| grok-bot | PRODUCTION ✅ | — | Telegram @Alaya_grokbot + xAI Grok |
| dashboard | PRODUCTION ✅ | — | Alaya Command Center |
| miniapp | PRODUCTION ✅ | — | Zangetsu Mini App |
| local-llm | PRODUCTION ✅ | 8001 | Qwen2.5-Coder-14B-Instruct (RTX 3080) |
| local-queue | PRODUCTION ✅ | — | Task queue daemon |
| network-watchdog | PRODUCTION ✅ | — | Network reliability |
| alaya-agent | STOPPED ⚠️ | — | Intentionally stopped 2026-03-20 16:14 |
| amadeus | DEAD ❌ | — | Service file exists, ~/projects/amadeus MISSING |
| king-crimson | DEAD ❌ | — | Service file exists, ~/projects/king-crimson MISSING |
| r-steiner | DEAD ❌ | — | Service file exists, ~/projects/r-steiner MISSING |
| dcbot | DEAD ❌ | — | Service file exists, ~/projects/dcbot MISSING |

---

## Running Services (Docker)

| Container | Status | Port | Notes |
|-----------|--------|------|-------|
| deploy-trader-1 | PRODUCTION ✅ | — | zangetsu paper_trader (BTC/USDT, LightGBM+Valkyrie) |
| deploy-ml_core-1 | PRODUCTION ✅ | — | zangetsu ML core (feature tournament, regime detection) |
| deploy-postgres-1 | PRODUCTION ✅ | 5432 | PostgreSQL 15 + pgvector |
| deploy-redis-1 | PRODUCTION ✅ | 6379 | Redis for zangetsu |
| deploy-dashboard-1 | PRODUCTION ✅ | 8080 | Zangetsu dashboard (gunicorn) |
| magi-litellm-1 | PRODUCTION ✅ | 4000 | LiteLLM proxy (claude-sonnet/opus/haiku) |
| magi-redis-1 | PRODUCTION ✅ | 6379 (lo) | Redis for LiteLLM |
| portainer | PRODUCTION ✅ | 9000 | Docker management UI |

---

## Project Specs (j13-ops/projects/)

| Spec | Status | Priority |
|------|--------|----------|
| P1-crimson-zangetsu-hybrid | SCAFFOLD | HIGH — connects zangetsu signals to real execution |
| P2-quant-signals-sub | SCAFFOLD | MEDIUM |
| P3-qbeyer-trader-persona | SCAFFOLD | LOW |
| P4-ai-chain-trader-dao | SCAFFOLD | LOW |
| P5-signal-router | SCAFFOLD | HIGH — critical missing link in signal chain |
| P6-zangetsu-api | SCAFFOLD | MEDIUM |
| P7-on-chain-ml-scanner | SCAFFOLD | LOW |
| P8-ops-console | SCAFFOLD | MEDIUM |

---

## P0 Issues (blocking)

1. **4 orphan service files**: amadeus, king-crimson, r-steiner, dcbot — all point to ~/projects/ which does not exist. Must be disabled and source documented.
2. **alaya-agent stopped**: was running, manually stopped 2026-03-20. Evaluate restart.
3. **zangetsu GH_TOKEN missing**: deploy-trader-1 has no GH_TOKEN env var — github_sync.py cannot push tournament results to GitHub.
4. **~/projects/ missing**: Docker containers reference this path as original build location. Source code lives inside images only — no git repo on disk.

## P1 Issues (important)

5. **GPU at 85% capacity**: 10.3/12GB VRAM (Qwen2.5-Coder-14B uses ~10GB). ML training jobs will OOM if GPU-enabled.
6. **Two Redis instances**: deploy-redis-1 (port 6379, internal docker) + magi-redis-1 (port 6379, localhost). No port conflict currently but confusing.
7. **No Prometheus/Grafana**: Observability mentioned in specs but not installed.
8. **LiteLLM bind mount gap**: Container mounts ~/projects/magi/litellm_config.yaml but that path doesn't exist. Container runs with embedded config — if restarted with compose, config may be empty dir.
