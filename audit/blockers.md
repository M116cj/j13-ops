# Blockers — 2026-03-21

Autonomous Phase 0-5 scan. Items below require j13 action or sudo access.

---

## B1 — PAT lacks `createRepository` scope

**Impact**: Cannot create new GitHub repos (e.g. `magi`, `signal-router`) autonomously.
**Action**: Generate a new PAT at github.com/settings/tokens with `repo` scope (write).
Store in `~/.config/gh/hosts.yml` on both Mac and alaya (replace current token).

---

## B2 — M116cj/zangetsu repo inaccessible via API

**Impact**: Cannot read zangetsu source from GitHub; github_sync.py in deploy-trader-1
has no GH_TOKEN env var — tournament results are not being pushed to GitHub.
**Action**:
1. Verify zangetsu repo exists (or create it).
2. Add `GH_TOKEN=<token_with_repo_write>` to the zangetsu deploy .env file.
3. Rebuild and redeploy the trader container.

---

## B3 — sudo required for SSH hardening and fail2ban

**Impact**: Cannot harden SSH config or install fail2ban autonomously.
**Recommendations** (run manually on alaya):
```bash
# 1. Install fail2ban
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban

# 2. Harden SSH (create override, do NOT edit sshd_config directly)
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf << 'EOF'
PasswordAuthentication no
PermitRootLogin no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
sudo systemctl reload ssh
```
**Note**: Do NOT change Port until Tailscale ACLs are updated to allow the new port.

---

## B4 — 4 orphan systemd service files

**Impact**: amadeus, king-crimson, r-steiner, dcbot are `enabled` but point to
`~/projects/` which does not exist. They spam systemd logs with restart failures.
**Services**: amadeus.service, king-crimson.service, r-steiner.service, dcbot.service
**Action** (run manually on alaya):
```bash
sudo systemctl disable --now amadeus king-crimson r-steiner dcbot
# Optionally archive the service files:
sudo mkdir -p /etc/systemd/system/archived
sudo mv /etc/systemd/system/{amadeus,king-crimson,r-steiner,dcbot}.service \
        /etc/systemd/system/archived/
sudo systemctl daemon-reload
```

---

## B5 — ~/projects/ directory missing (Docker source gone)

**Impact**: zangetsu, magi docker-compose files no longer on disk. Containers run
from pre-built images. If containers are stopped and compose is re-run, it will fail.
**Action**: Re-clone zangetsu from GitHub, or extract docker-compose.server.yml from
container labels and reconstruct it. Store in a version-controlled location.

---

## B6 — alaya-agent.service stopped since 2026-03-20

**Impact**: The agent.py planner+executor is not running. alaya-bot (bot.py) is
running as a fallback.
**Reason for stop**: Unknown (manual stop on Mar 20).
**Action**: Investigate logs, then restart if safe:
```bash
sudo systemctl start alaya-agent
journalctl -u alaya-agent -n 50
```

---

## B7 — LiteLLM bind mount source missing

**Impact**: /home/j13/projects/magi/litellm_config.yaml source path doesn't exist.
Container runs with config baked into image. On restart via compose, this will fail.
**Action**: Recreate ~/projects/magi/ with litellm_config.yaml (content is known
from docker exec inspect — see infra/litellm_config.yaml in this repo).

---

## Non-blocking (logged for awareness)

- GPU at 86% capacity (10.3/12 GB) — acceptable while training is CPU-only
- Two Redis instances on port 6379 (no conflict: one is docker-internal, one localhost)
- No TimescaleDB extension on PostgreSQL (evaluate separately)
