# Execution Blueprint 2026 — j13 Alaya Stack

> This document is the primary deliverable of the Strategic Research directive.
> Detailed enough that any agent can execute with zero ambiguity.
> All phases are in dependency order. Each phase has a clear entry condition and exit criterion.

---

## PART 5A. Phase Sequencing

### Phase 0 — Security Hardening (ENTRY: sudo access, 30 min)
*Entry condition*: j13 has sudo on alaya.
*Exit criterion*: No services exposed to 0.0.0.0 except via intentional firewall rules.

**Step 0.1 — Firewall**
```bash
sudo ufw allow from 100.64.0.0/10 to any   # Tailscale CGNAT
sudo ufw allow 22/tcp                        # SSH
sudo ufw deny 4000/tcp                       # LiteLLM — no public access
sudo ufw deny 8080/tcp                       # zangetsu dashboard
sudo ufw deny 9000/tcp                       # Portainer
sudo ufw deny 7700/tcp                       # miniapp
sudo ufw --force enable
sudo ufw status verbose
```

**Step 0.2 — LiteLLM localhost binding**
Edit `~/j13-ops/infra/litellm/docker-compose.yml`:
- Change `ports: - "4000:4000"` to `ports: - "127.0.0.1:4000:4000"`
- Rotate master_key: generate with `openssl rand -hex 32`
- Store new key in `.env` file (not in YAML)
```bash
cd ~/j13-ops/infra/litellm && docker compose up -d --force-recreate
```

**Step 0.3 — Portainer localhost binding**
```bash
# Edit portainer container or replace with: -p 127.0.0.1:9000:9000
docker stop portainer && docker rm portainer
docker run -d --name portainer --restart=unless-stopped \
  -p 127.0.0.1:9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  portainer/portainer-ce:latest
```

**Step 0.4 — fail2ban + SSH hardening**
```bash
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf << 'EOF'
PasswordAuthentication no
PermitRootLogin no
MaxAuthTries 3
ClientAliveInterval 300
EOF
sudo systemctl reload ssh
```

**Verification**: `sudo ufw status` shows all 4 ports DENY or not listed. `curl http://localhost:4000/health` works. `curl http://ALAYA_IP:4000/health` times out.

---

### Phase 1 — Immediate Fixes (ENTRY: Phase 0 complete OR can run in parallel, 1–2 hours)
*Entry condition*: None — these are independent.
*Exit criterion*: echelon delivers signals to Telegram; alaya-agent running; miniapp shows real data.

**Step 1.1 — Fix echelon Telegram delivery**

The fixed `send_telegram` function with thread fallback exists at `/tmp/echelon/echelon.py` on Mac.

```bash
# On Mac:
scp /tmp/echelon/echelon.py j13@100.123.49.102:~/j13-ops/infra/echelon/echelon.py
ssh j13@100.123.49.102 "cd ~/j13-ops/infra/echelon && docker compose build && docker compose up -d --force-recreate echelon"
```

Verify:
```bash
ssh j13@100.123.49.102 "docker logs echelon --tail 20"
```
Expected: `Telegram sent OK (thread=False)` or `Telegram sent OK (thread=True)` in logs within 15 seconds if a new signal exists.

**Step 1.2 — Restart alaya-agent**
```bash
ssh j13@100.123.49.102 "sudo systemctl start alaya-agent && systemctl status alaya-agent"
```

Add watchdog (prevents silent death):
```bash
ssh j13@100.123.49.102 "sudo tee /etc/systemd/system/alaya-agent.service.d/watchdog.conf << 'EOF'
[Service]
WatchdogSec=60
Restart=on-failure
RestartSec=10
EOF
sudo systemctl daemon-reload && sudo systemctl restart alaya-agent"
```

**Step 1.3 — Fix miniapp**

miniapp/main.py currently queries `strategies` table (Railway schema — doesn't exist).
Replace with queries against actual zangetsu tables: `execution_log`, `champions`, `live_elo`.

Target API endpoints:
- `GET /api/zangetsu` → last 10 execution_log entries + current champion info
- `GET /api/health` → container health summary

```python
# New /api/zangetsu handler (replace existing):
@app.get("/api/zangetsu")
async def zangetsu_status():
    try:
        conn = await asyncpg.connect(POOL_DATABASE_URL)
        signals = await conn.fetch(
            "SELECT id, entry_ts, side, price, confidence FROM execution_log "
            "ORDER BY id DESC LIMIT 10"
        )
        champion = await conn.fetchrow(
            "SELECT model_id, elo_score, win_rate FROM live_elo "
            "ORDER BY elo_score DESC LIMIT 1"
        )
        await conn.close()
        return {
            "recent_signals": [dict(s) for s in signals],
            "champion": dict(champion) if champion else None,
            "signal_count": {"total": 52, "buy": 27, "sell": 25}
        }
    except Exception as e:
        return {"error": str(e)}
```

Deploy:
```bash
ssh j13@100.123.49.102 "sudo systemctl restart miniapp && curl http://localhost:7700/api/zangetsu"
```

---

### Phase 2 — Source Recovery and Version Control (ENTRY: Phase 1 complete, 4–6 hours)
*Entry condition*: echelon working, alaya-agent running.
*Exit criterion*: zangetsu source on GitHub with all container source code.

**Step 2.1 — Extract zangetsu source from Docker images**

```bash
# On alaya, extract each service's source:
docker create --name extract-trader deploy-trader && \
  docker cp extract-trader:/app ./zangetsu-trader-src && \
  docker rm extract-trader

docker create --name extract-mlcore deploy-ml_core && \
  docker cp extract-mlcore:/app ./zangetsu-mlcore-src && \
  docker rm extract-mlcore

docker create --name extract-dash deploy-dashboard && \
  docker cp extract-dash:/app ./zangetsu-dash-src && \
  docker rm extract-dash
```

**Step 2.2 — Create GitHub repo and push**

Requirements: PAT with `repo` scope (current PAT is read-only — j13 must create new one).

```bash
gh repo create M116cj/zangetsu --private --description "Quant trading system"
cd zangetsu-trader-src
git init && git add . && git commit -m "chore: recover source from Docker image"
git remote add origin https://github.com/M116cj/zangetsu.git
git push -u origin main
```

**Step 2.3 — Add GH_TOKEN to deploy environment**

```bash
# Edit ~/j13-ops/deploy/.env (or wherever zangetsu env lives):
echo "GH_TOKEN=<new_pat_with_repo_write>" >> ~/j13-ops/deploy/.env
```

---

### Phase 3 — Market Data Pipeline (ENTRY: Phase 2 complete, 6–8 hours)
*Entry condition*: zangetsu source visible and on GitHub.
*Exit criterion*: ohlcv_1m populated with real OHLCV data; ml_core training on real data.

**Step 3.1 — Audit zangetsu data ingestion code**

After source extraction, find the OHLCV ingestion module:
```bash
grep -r "ohlcv" zangetsu-trader-src/ --include="*.py" -l
grep -r "fetch_ohlcv\|ohlcv_1m\|INSERT.*ohlcv" zangetsu-trader-src/ --include="*.py"
```

**Step 3.2 — Identify why ohlcv_1m is empty**

Options:
- (a) Ingestion never implemented — need to write it
- (b) Ingestion disabled by config flag
- (c) Ingestion failing silently
- (d) Different data source used

Determine by inspecting source. Then fix.

**Step 3.3 — Backfill OHLCV data**

Using ccxt (Binance):
```python
import ccxt
binance = ccxt.binance({'enableRateLimit': True})
ohlcv = binance.fetch_ohlcv('BTC/USDT', '1m', limit=1000)
# INSERT into ohlcv_1m (ts, open, high, low, close, volume)
```

Verify: `SELECT COUNT(*), MAX(ts), MIN(ts) FROM ohlcv_1m;`

**Step 3.4 — Validate ml_core trains on real data**

After ohlcv_1m is populated:
```bash
docker restart deploy-ml_core-1
docker logs deploy-ml_core-1 --follow --tail 50
```
Expected: LightGBM training log with non-zero feature count.

---

### Phase 4 — Valkyrie Validation (ENTRY: Phase 3 complete OR parallel to 3, 3 hours)
*Entry condition*: 52 execution_log entries available NOW. Can start before Phase 3.
*Exit criterion*: valkyrie produces a PASS/FAIL verdict on paper-trading performance.

**Step 4.1 — Run valkyrie against execution_log**

```bash
# Query execution_log for paper trading results:
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -c \
  "SELECT entry_ts, side, price, confidence, leverage FROM execution_log ORDER BY entry_ts"

# Extract to CSV:
docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -c \
  "\COPY execution_log TO '/tmp/signals.csv' CSV HEADER"
docker cp deploy-postgres-1:/tmp/signals.csv ./signals.csv
```

**Step 4.2 — Interpret valkyrie results**

valkyrie.py performs:
- Monte Carlo permutation test (is performance above random?)
- Purged CPCV walk-forward validation (does it generalize across time?)

With only 52 signals, sample size is statistically marginal. But the test will reveal if the win rate (27 BUY / 25 SELL balance) is meaningful.

**Decision gate**: valkyrie PASS = proceed to live trading. valkyrie FAIL = debug regime detection before live trading.

---

### Phase 5 — Live Trading Readiness (ENTRY: Phases 0–4 all PASS, 2 hours)
*Entry condition*: Security hardened, source version-controlled, ohlcv_1m populated, valkyrie PASS, echelon delivering signals.
*Exit criterion*: Paper trading → live trading switch with risk controls in place.

**Step 5.1 — Pre-flight checklist**

- [ ] Firewall active, no ports exposed to internet
- [ ] echelon delivers signals to Telegram in real-time
- [ ] ohlcv_1m has >10,000 rows of historical data
- [ ] LightGBM champion has been trained on real data
- [ ] valkyrie PASS on at least 30-day paper trade
- [ ] Circuit breaker limits configured (circuit_breaker_log table exists)
- [ ] zangetsu source on GitHub
- [ ] Rollback plan: `docker compose down trader && docker compose up -d trader` with previous image

**Step 5.2 — Switch from paper to live**

```bash
# Edit zangetsu .env:
# TRADE_MODE=paper → TRADE_MODE=live
# BINANCE_API_KEY=<real key>
# BINANCE_SECRET=<real secret>
# Set position size limit: MAX_POSITION_USD=100  (start small)
docker compose up -d --force-recreate trader
```

**Step 5.3 — Monitor first 24 hours**

- Check execution_log every hour for new signals
- Monitor echelon → Telegram delivery
- Watch circuit_breaker_log for any breach
- Grafana: container health, DB query times

---

## 5B. Infrastructure Improvements (Parallel to Phases 1–5)

These can run anytime, independent of the main trading pipeline phases.

### INF-1: uv Migration (0.5h each project)
```bash
# For each project on alaya:
cd ~/agent && pip install uv && uv init && uv add $(cat requirements.txt | tr '\n' ' ')
# Replace `pip install -r requirements.txt` with `uv sync` in deploy.sh
```

### INF-2: uvloop (5 min per bot)
Add to top of agent.py, bot.py, echelon.py:
```python
import uvloop
uvloop.install()  # replaces asyncio event loop
```
Add `uvloop` to requirements.

### INF-3: Remove orphan systemd units (5 min, needs sudo)
```bash
sudo systemctl disable amadeus king-crimson r-steiner dcbot
sudo rm /etc/systemd/system/{amadeus,king-crimson,r-steiner,dcbot}.service
sudo systemctl daemon-reload
```

### INF-4: Remove unused deploy-redis-1
Only after zangetsu code confirms zero Redis usage:
```bash
cd ~/j13-ops/deploy && grep -r "redis" . --include="*.py"
# If zero results:
docker stop deploy-redis-1 && docker rm deploy-redis-1
# Edit docker-compose.yml to remove redis service
```

---

## 5C. Decision Gates

| Gate | Condition | If PASS | If FAIL |
|------|-----------|---------|---------|
| G1 — Source Recovery | zangetsu source extracted and on GitHub | proceed to Phase 3 | escalate to j13: need new PAT + manual extraction |
| G2 — OHLCV Pipeline | ohlcv_1m row count >10,000 after 24h | proceed to Phase 4 | debug ingestion code |
| G3 — valkyrie | Monte Carlo p-value < 0.05 + CPCV pass | proceed to Phase 5 | debug LightGBM regime detection |
| G4 — Security | No ports on 0.0.0.0 except intentional | proceed to live trading | block live trading |
| G5 — Echelon | Signals in Telegram within 60s of generation | proceed | fix Telegram bot config |

---

## 5D. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| zangetsu Docker image cleared before source extracted | low | CRITICAL | Extract source in Phase 2 before any Docker operations |
| Live trade hits unexpected leverage and exceeds capital | medium | HIGH | MAX_POSITION_USD hard limit in env; circuit breaker |
| Qwen crashes during live trading inference | medium | MEDIUM | systemd restart, trading does not depend on Qwen |
| PostgreSQL disk full | low | CRITICAL | Disk is 6% used (52G/915G) — monitor quarterly |
| Binance API rate limit | medium | LOW | ccxt handles this; paper mode already using it |
| LiteLLM key exposed before rotation | high (currently) | HIGH | Phase 0 Step 0.2 — first action |

---

## Quick Reference: Order of Operations

```
TODAY (< 2 hours total):
  ├── Phase 0.1: ufw firewall (needs sudo) — blocks external exposure
  ├── Phase 0.2: LiteLLM localhost binding — stops API key exposure
  ├── Step 1.1: SCP + rebuild echelon — signals start working
  ├── Step 1.2: Restart alaya-agent + watchdog
  └── Step 1.3: Fix miniapp (65 LOC rewrite)

THIS WEEK:
  ├── Phase 0.4: fail2ban + SSH hardening (needs sudo)
  ├── Phase 2: Source recovery — needs new GitHub PAT from j13
  └── Phase 4: Valkyrie validation — can start NOW with 52 signals

NEXT WEEK:
  ├── Phase 3: OHLCV pipeline (needs Phase 2 first)
  └── INF-1/2/3/4: uv, uvloop, orphan cleanup, Redis removal

WHEN GATES PASS:
  └── Phase 5: Live trading
```

---

*Blueprint produced: 2026-03-21. Research basis: ground-truth-inventory.md + system-dependency-map.md + tech-landscape-2026.md + gap-analysis.md.*
