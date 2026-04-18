# j13-ops

Infrastructure configurations, deployment scripts, and operational tooling for j13's private systems.

---

## What's Here

| Directory | Purpose |
|-----------|---------|
| `infra/` | Server configs, Docker Compose, Caddy, observability, LiteLLM config, GPU coordinator |
| `calcifer/` | Alaya infrastructure guardian agent (Gemma4 E4B) — supervisor, notifier, hypotheses, skills |
| `zangetsu/` | Zangetsu quant engine — services, engine, live, migrations, dashboard, ctl + watchdog, VERSION_LOG |

> Historical note: `agent_bus/` and `markl/` were removed on 2026-04-18 during environment cleanup.
> `bots/`, `scripts/`, `monitoring/` directories never materialized under this repo — those
> concerns live inside `infra/observability/`, `zangetsu/scripts/`, and `calcifer/` respectively.

---

## Systems Managed

- **Nexus** — AI agent mesh (Claude + Grok + Qwen + Gemini)
- **Nexus Console** — React SSE dashboard at port 8767
- **r-steiner** — Autonomous X publishing pipeline
- **Zangetsu** — Quantitative ML tournament engine (V10 GP Alpha Expression)
- **Calcifer** — Alaya infrastructure guardian (auto-diagnostics, pre/post-deploy sanity)

---

## Server

Self-hosted · RTX 3080 12GB · Tailscale mesh network  
Access: `ssh j13@100.123.49.102` (Tailscale only)

---

> Private operations repo. No secrets committed.

---

_Last updated: 2026-04-18_
