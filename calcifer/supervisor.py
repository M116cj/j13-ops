"""Calcifer v3 — Hermes-grade Alaya & AKASHA Operations Agent.

Full capabilities: context compression, error recovery, multi-turn tool chaining,
skill system, trajectory recording, self-correction, interactive Telegram.
"""
import os, sys, json, time, subprocess, signal, fcntl, atexit
from datetime import datetime, timezone
from hypotheses import HypothesisManager
from notifier import process_finding
from agent_core import (
    ContextManager, ErrorRecovery, chain_tools,
    SkillManager, TrajectoryRecorder, parse_json_safe,
    EvolutionEngine, LiteLLMClient, TechScout, TaskTracker,
    ScheduledReporter, OperationGuard, AgentBus, ToolTracker,
)

OLLAMA_URL = "http://localhost:11434"
MODEL = "gemma4:e4b"
BOT_TOKEN = "8237499581:AAFfSngYTSmsmVHPCMMFw0g7kkXpOj5kDFU"
OWNER_ID = 5252897787
POLL_INTERVAL = 2
HEALTH_INTERVAL = 300
BASE_DIR = os.path.expanduser("~/j13-ops/calcifer")
LOG_FILE = os.path.join(BASE_DIR, "calcifer.log")
LOCK_FILE = "/tmp/zangetsu/calcifer_supervisor.lock"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

_lock_fd = None
def acquire_lock():
    global _lock_fd
    _lock_fd = open(LOCK_FILE, "a+")
    try:
        fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print("[calcifer] Another instance running.", file=sys.stderr); sys.exit(1)
    _lock_fd.seek(0); _lock_fd.truncate(); _lock_fd.write(str(os.getpid())); _lock_fd.flush()
    atexit.register(lambda: _lock_fd and fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN))
acquire_lock()

ctx = ContextManager(max_tokens=6000)
skills = SkillManager(os.path.join(BASE_DIR, "skills"))
trajectory = TrajectoryRecorder(BASE_DIR)
hyp_mgr = HypothesisManager(BASE_DIR)
evolution = EvolutionEngine(BASE_DIR, "_global", "calcifer")
litellm = LiteLLMClient()
tech_scout = TechScout(litellm, "calcifer",
    "You manage: Alaya server (Docker 20+ containers, PostgreSQL, AKASHA memory system, "
    "Ollama LLM, LiteLLM proxy, Grafana/Prometheus monitoring, Caddy reverse proxy, GPU compute). "
    "Tech stack: Docker, systemd, PostgreSQL, Redis, Nginx/Caddy, Python, Tailscale VPN.",
    BASE_DIR)
task_tracker = TaskTracker(BASE_DIR)
reporter = ScheduledReporter(BASE_DIR)
agent_bus = AgentBus("calcifer")
tool_tracker = ToolTracker(BASE_DIR)

def log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = json.dumps({"ts": ts, "level": level, "msg": str(msg)[:300]})
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def ask_llm(prompt, max_tokens=1024):
    import urllib.request
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.3},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    def _call():
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read()).get("response", "").strip()
    result = ErrorRecovery.with_retry(_call)
    return result if isinstance(result, str) else ""

def tg_api(method, data=None):
    import urllib.request
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}) if body else urllib.request.Request(url)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        log("ERROR", f"TG {method}: {e}")
        return {"ok": False}

def tg_send(text, chat_id=OWNER_ID):
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        tg_api("sendMessage", {"chat_id": chat_id, "text": chunk})

def run_cmd(cmd, timeout=30):
    def _run():
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()[:3000]
    return ErrorRecovery.with_retry(_run)

TOOLS = {
    "check_docker": lambda: run_cmd("docker ps --format 'table {{.Names}}\\t{{.Status}}' 2>&1 | head -30"),
    "check_disk": lambda: run_cmd("df -h / /home 2>&1"),
    "check_memory": lambda: run_cmd("free -h | head -2"),
    "check_load": lambda: run_cmd("uptime"),
    "check_gpu": lambda: run_cmd("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo 'no GPU'"),
    "check_network": lambda: run_cmd("curl -s --connect-timeout 3 https://api.telegram.org -o /dev/null -w '%{http_code}' 2>&1 || echo 'OFFLINE'"),
    "check_akasha_api": lambda: run_cmd("curl -s --connect-timeout 3 http://100.123.49.102:8769/health 2>&1"),
    "check_akasha_db": lambda: run_cmd("docker exec akasha-postgres psql -U akasha -d akasha -t -c \"SELECT 'chunks=' || count(*) FROM memory_chunks\" 2>&1 || echo 'unreachable'"),
    "check_akasha_redis": lambda: run_cmd("docker exec akasha-redis redis-cli ping 2>&1"),
    "check_zangetsu": lambda: run_cmd("~/j13-ops/zangetsu/zangetsu_ctl.sh status 2>&1 | head -15"),
    "check_ollama": lambda: run_cmd("curl -s http://localhost:11434/api/tags 2>&1 | head -5"),
    "check_litellm": lambda: run_cmd("curl -s --connect-timeout 3 http://localhost:4000/health 2>&1 | head -5 || echo 'DOWN'"),
    "check_db_health": lambda: run_cmd("docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -c \"SELECT 'rows=' || count(*) || ' deployable=' || count(*) FILTER (WHERE status='DEPLOYABLE') FROM champion_pipeline\" 2>&1"),
    "check_backups": lambda: run_cmd("echo PG: && ls -lh /home/j13/backups/*.sql.gz 2>/dev/null | tail -3 && echo Redis: && ls -lh /home/j13/backups/*.rdb 2>/dev/null | tail -3 || echo no backups found"),
    "check_rsteiner": lambda: run_cmd("tail -5 ~/r-steiner/data/run.log 2>/dev/null && echo --- && ps aux | grep r-steiner | grep -v grep | wc -l && echo processes"),
    "check_logs": lambda: run_cmd("tail -30 ~/j13-ops/zangetsu/logs/engine.jsonl 2>/dev/null | grep -i 'error\\|fail\\|warn' | tail -10 || echo 'no errors'"),
}

SYSTEM_KNOWLEDGE = """Alaya Infrastructure:
Server: i7-12700K, 32GB RAM, 20 cores, RTX 12GB, 915GB NVMe
Docker services (20+): deploy-postgres-1, akasha-postgres, akasha-redis, akasha-harness(:8769), magi-litellm-1(:4000), obs-grafana/prometheus/alertmanager, portainer, claude-inbox(:8765), d-mail-miniapp, katen-collector
R-Steiner: Automated research platform (6 cron jobs, runs scheduler/series/progress/kol_preconfig/monitor)
Backups: pg-backup daily 02:00, redis-backup daily 03:00, redis-trim daily 04:00
Zangetsu Pipeline: 6x A1 workers + A23 + A45 + A13 (managed by zangetsu_ctl.sh)
Dependencies:
- Zangetsu → deploy-postgres-1
- AKASHA → akasha-postgres + akasha-redis
- LiteLLM → network + API keys
- If postgres dies → pipeline + dashboard stop
- If AKASHA dies → Claude loses project memory
- If Ollama dies → Calcifer + Markl lose LLM"""

def handle_message(text):
    trajectory.record("user", text)
    ctx.add("user", text)

    tools_desc = ", ".join(TOOLS.keys())
    skill_content = skills.skills_full_context(1500)
    user_interests = trajectory.user_interests()
    tool_eff = tool_tracker.effectiveness_summary()

    prompt = f"""You are Calcifer, self-evolving Alaya & AKASHA operations manager.
{SYSTEM_KNOWLEDGE}

{skill_content}

{user_interests}

{tool_eff}

Conversation context:
{ctx.get_prompt_context(2000)}

Available tools: {tools_desc}

j13's message: "{text}"

Instructions:
- To check something, respond: TOOL: tool_name
- You can chain multiple tools
- Answer in 繁體中文
- 直接回答 → 帶出關聯 → 影響分析"""

    response = chain_tools(
        ask_llm_fn=ask_llm,
        tools=TOOLS,
        initial_prompt=prompt,
        max_turns=3,
        log_fn=log,
    )

    ctx.add("assistant", response)
    trajectory.record("assistant", response)
    return response

def run_health_cycle(cycle):
    log("INFO", f"Health cycle #{cycle}")
    evo_ctx = evolution.pre_cycle_context()
    if evo_ctx:
        log("INFO", f"Evolution context loaded ({len(evo_ctx)} chars)")
    snapshot = {name: fn() for name, fn in TOOLS.items()}
    log("INFO", f"Observed: {len(snapshot)} checks")

    recent = []
    ff = os.path.join(BASE_DIR, "findings.jsonl")
    if os.path.exists(ff):
        recent = [json.loads(l) for l in open(ff).readlines()[-10:]]

    prompt = f"""You are Calcifer, self-evolving Alaya & AKASHA ops manager.

{evo_ctx}

System state:
{json.dumps(snapshot, indent=2)[:2500]}

Previous findings: {json.dumps([f.get('summary', f.get('insight','')) for f in recent[-3:]])}

Identify 1-3 issues. JSON array: [{{"hypothesis":"...","verify_tool":"...","confirm_pattern":"..."}}]
If healthy: []"""

    response = ask_llm(prompt, 600)
    hypotheses = parse_json_safe(response) or []
    if isinstance(hypotheses, dict):
        hypotheses = [hypotheses]
    hypotheses = [h for h in hypotheses if isinstance(h, dict) and not hyp_mgr.is_already_tested(h.get("hypothesis",""))]

    for h in hypotheses[:3]:
        tool = h.get("verify_tool", "")
        result = TOOLS[tool]() if tool in TOOLS else "[unknown]"
        eval_prompt = f"""Hypothesis: {h.get('hypothesis','')}
Expected: {h.get('confirm_pattern','')}
Result: {result[:1500]}
JSON: {{"confirmed":true/false,"severity":"critical|warning|info","summary":"...","action_needed":true/false}}"""
        evaluation = parse_json_safe(ask_llm(eval_prompt, 200)) or {"confirmed": False}

        if evaluation.get("confirmed"):
            finding = {"cycle": cycle, "ts": datetime.now(timezone.utc).isoformat(),
                       "hypothesis": h.get("hypothesis",""), "confirmed": True,
                       "severity": evaluation.get("severity","info"),
                       "summary": evaluation.get("summary",""),
                       "action_needed": evaluation.get("action_needed", False)}
            hyp_mgr.record(h.get("hypothesis",""), "CONFIRMED", evaluation)
            hyp_mgr.record_finding(finding)
            process_finding("_global", "calcifer", finding)
            tg_send(f"🔥 CALCIFER\n[{finding['severity']}] {finding['summary']}")
            agent_bus.send("markl", f"[{finding['severity']}] {finding['summary']}", finding['severity'])
        else:
            hyp_mgr.record(h.get("hypothesis",""), "REJECTED", evaluation)

    # Post-cycle evolution
    ff = os.path.join(BASE_DIR, "findings.jsonl")
    new_findings = []
    if os.path.exists(ff):
        new_findings = [json.loads(l) for l in open(ff).readlines() if json.loads(l).get("cycle") == cycle]
    if new_findings:
        evolution.post_cycle_evolve(cycle, new_findings, ask_llm)
        log("INFO", f"Evolution: reflected on {len(new_findings)} findings")
    log("INFO", f"Health cycle #{cycle} done")

def main():
    log("INFO", "Calcifer v3 (Hermes-grade) starting")
    tg_send("🔥 CALCIFER v3 ONLINE\nAlaya & AKASHA 運營主管已啟動\n功能: 多輪工具調用 + 錯誤恢復 + skill 系統\n\n發送任何訊息開始互動")

    running = True
    last_update_id = 0
    health_cycle = 0
    last_health = 0
    last_scout = 0
    SCOUT_INTERVAL = 21600

    def handle_sig(s, f):
        nonlocal running; running = False
    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    while running:
        try:
            updates = tg_api("getUpdates", {"offset": last_update_id + 1, "timeout": 1})
            if updates.get("ok"):
                for upd in updates.get("result", []):
                    last_update_id = upd["update_id"]
                    msg = upd.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")
                    if not text or msg.get("from", {}).get("id") != OWNER_ID:
                        continue
                    log("INFO", f"j13: {text[:100]}")
                    tg_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
                    if any(kw in text.lower() for kw in ["研究", "調查", "幫我", "追蹤", "檢查一下"]):
                        task = task_tracker.add(text)
                        log("INFO", f"Task #{task['id']} created")
                    response = handle_message(text)
                    pending = task_tracker.pending()
                    if pending:
                        response += f"\n\n📋 待辦: {len(pending)} 個任務"
                    tg_send(response, chat_id)
        except Exception as e:
            log("ERROR", f"Poll: {e}")

        now = time.time()

        if now - last_health > HEALTH_INTERVAL:
            health_cycle += 1
            try:
                run_health_cycle(health_cycle)
            except Exception as e:
                log("ERROR", f"Health: {e}")
            last_health = now

        if now - last_scout > SCOUT_INTERVAL:
            try:
                log("INFO", "Tech scout starting")
                findings = tech_scout.scout()
                report = tech_scout.format_report(findings)
                if report:
                    tg_send(report)
                    log("INFO", f"Tech scout: {len(findings)} findings")
            except Exception as e:
                log("ERROR", f"Tech scout: {e}")
            last_scout = now

        # Check cross-agent messages from Markl
        try:
            msgs = agent_bus.receive()
            for m in msgs:
                log("INFO", f"Bus msg from {m['from']}: {m['message'][:80]}")
                tg_send(f"📨 來自 Markl: {m['message']}")
        except Exception:
            pass

        if reporter.should_daily():
            try:
                data = {name: fn() for name, fn in list(TOOLS.items())[:5]}
                summary = ask_llm(f"Summarize system health in 3-5 bullets (繁體中文):\n{json.dumps(data, indent=2)[:2000]}", 300)
                tg_send(f"🔥 CALCIFER 每日報告\n{summary}\n\n{task_tracker.summary()}")
                reporter.mark_daily()
            except Exception as e:
                log("ERROR", f"Daily report: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
