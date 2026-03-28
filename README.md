# j13-ops

Infrastructure configurations, deployment scripts, and operational tooling for j13's private systems.

---

## What's Here

| Directory | Purpose |
|-----------|---------|
| `infra/` | Server configs, Docker Compose files, nginx, UFW rules |
| `bots/` | Telegram bot service configs |
| `scripts/` | Deployment and maintenance scripts |
| `monitoring/` | Health check scripts and alert configs |

---

## Systems Managed

- **Nexus** — AI agent mesh (Claude + Grok + Qwen + Gemini)
- **Nexus Console** — React SSE dashboard at port 8767
- **r-steiner** — Autonomous X publishing pipeline
- **Zangetsu** — Quantitative ML tournament engine

---

## Server

Self-hosted · RTX 3080 12GB · Tailscale mesh network  
Access: `ssh j13@100.123.49.102` (Tailscale only)

---

> Private operations repo. No secrets committed.
