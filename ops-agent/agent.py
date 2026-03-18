"""
ops-agent — autonomous server monitoring and self-repair agent.

Runs every CHECK_INTERVAL_MIN minutes (default 5).
Uses Ollama (qwen2.5:7b) for anomaly diagnosis and rule-based auto-repair.
Reports to Telegram.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import psutil
import schedule

import telegram
from ollama_client import analyze

# ---------------------------------------------------------------------------
# Configuration — all overridable via environment variables
# ---------------------------------------------------------------------------
CHECK_INTERVAL_MIN   = int(os.environ.get("CHECK_INTERVAL_MIN",   "5"))
GPU_TEMP_THRESHOLD   = int(os.environ.get("GPU_TEMP_THRESHOLD",   "85"))
DISK_THRESHOLD_PCT   = int(os.environ.get("DISK_THRESHOLD_PCT",   "90"))
RAM_THRESHOLD_PCT    = int(os.environ.get("RAM_THRESHOLD_PCT",    "90"))
MAX_RESTART_ATTEMPTS = int(os.environ.get("MAX_RESTART_ATTEMPTS", "3"))
RESTART_WINDOW_MIN   = int(os.environ.get("RESTART_WINDOW_MIN",  "30"))

# Containers that should always be auto-restarted when they exit
AUTO_RESTART_ALWAYS = {
    "zangetsu-tier1", "zangetsu-tier2", "zangetsu-tier3",
    "amadeus", "portainer", "portainer-agent", "cloudflared",
}

# Containers to skip entirely (comma-separated env var)
_skip_raw = os.environ.get("SKIP_CONTAINERS", "")
SKIP_CONTAINERS: set[str] = {
    c.strip() for c in _skip_raw.split(",") if c.strip()
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ops-agent")

# ---------------------------------------------------------------------------
# In-memory crash counter  {container_name: [epoch_timestamp, ...]}
# ---------------------------------------------------------------------------
crash_log: dict[str, list[float]] = defaultdict(list)

# Daily event log for the 09:00 UTC summary
daily_events: list[str] = []


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _now_utc().strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess command. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "command timed out"
    except Exception as e:
        return 1, "", str(e)


def get_containers() -> list[dict]:
    """Return list of container dicts from `docker ps -a --format json`."""
    rc, out, err = _run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if rc != 0:
        log.error("docker ps failed: %s", err)
        return []
    containers = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            log.warning("Could not parse docker ps line: %s", line)
    return containers


def get_container_logs(name: str, tail: int = 20) -> str:
    """Return last N lines of a container's logs."""
    rc, out, err = _run(["docker", "logs", "--tail", str(tail), name], timeout=15)
    return out or err or "(no logs)"


def restart_container(name: str) -> bool:
    """Attempt to restart a container. Returns True on success."""
    rc, out, err = _run(["docker", "restart", name], timeout=30)
    if rc == 0:
        log.info("Restarted container: %s", name)
        return True
    log.error("Failed to restart %s: %s", name, err)
    return False


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def get_gpu_temp() -> int | None:
    """Return GPU temperature in Celsius, or None if nvidia-smi unavailable."""
    rc, out, err = _run(
        ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
        timeout=10,
    )
    if rc != 0 or not out:
        return None
    try:
        return int(out.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def get_disk_pct() -> float:
    """Return root disk usage as a percentage (0–100)."""
    usage = shutil.disk_usage("/")
    return usage.used / usage.total * 100


def get_ram_pct() -> float:
    """Return RAM usage as a percentage (0–100)."""
    mem = psutil.virtual_memory()
    return mem.percent


def get_cpu_pct() -> float:
    """Return 1-second CPU usage percentage."""
    return psutil.cpu_percent(interval=1)


# ---------------------------------------------------------------------------
# Crash-counter helpers
# ---------------------------------------------------------------------------

def _purge_old_crashes(name: str) -> None:
    """Remove crash timestamps older than RESTART_WINDOW_MIN from memory."""
    cutoff = time.time() - RESTART_WINDOW_MIN * 60
    crash_log[name] = [t for t in crash_log[name] if t >= cutoff]


def crash_count_in_window(name: str) -> int:
    _purge_old_crashes(name)
    return len(crash_log[name])


def record_crash(name: str) -> None:
    _purge_old_crashes(name)
    crash_log[name].append(time.time())


# ---------------------------------------------------------------------------
# Repair + notification logic
# ---------------------------------------------------------------------------

def handle_exited_container(container: dict) -> None:
    name = container.get("Names", "unknown")
    status = container.get("Status", "")
    logs = get_container_logs(name)
    count = crash_count_in_window(name)

    log.info("Container %s is down. Crashes in window: %d", name, count)

    # Decide via LLM first (best-effort; falls back to rule-based)
    prompt = (
        f"Server ops issue detected. Container '{name}' exited with status '{status}'.\n"
        f"Last logs:\n{logs}\n\n"
        "Should I: (a) restart it (b) alert only (c) investigate further?\n"
        'Reply with JSON: {"action": "restart"|"alert"|"investigate", '
        '"reason": "...", "telegram_msg": "..."}'
    )
    llm = analyze(prompt)
    ai_action   = llm.get("action", "alert")
    ai_reason   = llm.get("reason", "N/A")
    ai_tg_msg   = llm.get("telegram_msg", "")

    # Rule-based override: too many crashes → alert only
    if count >= MAX_RESTART_ATTEMPTS:
        action = "alert"
        action_note = f"⛔ Max restart attempts ({MAX_RESTART_ATTEMPTS}) reached in window — no restart"
    elif name in AUTO_RESTART_ALWAYS or ai_action == "restart":
        action = "restart"
        action_note = ""
    else:
        action = "alert"
        action_note = "ℹ️ Rule: alert only"

    # Execute
    taken = ""
    if action == "restart":
        record_crash(name)
        attempt = crash_count_in_window(name)
        success = restart_container(name)
        taken = (
            f"✅ Action taken: restarted (attempt {attempt}/{MAX_RESTART_ATTEMPTS})"
            if success
            else f"❌ Restart failed (attempt {attempt}/{MAX_RESTART_ATTEMPTS})"
        )
    else:
        taken = action_note or "🔔 Alert sent — no restart"

    tail_log = logs.splitlines()[-1] if logs.splitlines() else "(none)"

    msg = (
        f"🔴 <b>[j13-server] Container DOWN: {name}</b>\n"
        f"📋 Last log: <code>{tail_log}</code>\n"
        f"🤖 AI diagnosis: {ai_reason}\n"
        f"{taken}\n"
        f"⏰ {_ts()}"
    )
    if action_note:
        msg += f"\n{action_note}"
    if ai_tg_msg and ai_tg_msg != taken:
        msg += f"\n{ai_tg_msg}"

    telegram.send(msg)

    event_summary = f"[{_ts()}] Container {name} DOWN — {taken}"
    daily_events.append(event_summary)
    log.info(event_summary)


def handle_gpu_temp(temp: int) -> None:
    msg = (
        f"🌡️ <b>[j13-server] GPU Temp Alert: {temp}°C</b>\n"
        f"Threshold: {GPU_TEMP_THRESHOLD}°C\n"
        f"⏰ {_ts()}"
    )
    telegram.send(msg)
    daily_events.append(f"[{_ts()}] GPU temp {temp}°C (threshold {GPU_TEMP_THRESHOLD}°C)")
    log.warning("GPU temp alert: %d°C", temp)


def handle_disk_alert(pct: float) -> None:
    log.warning("Disk usage high: %.1f%%. Running docker system prune.", pct)
    rc, out, err = _run(["docker", "system", "prune", "-f"], timeout=120)
    prune_result = "prune succeeded" if rc == 0 else f"prune failed: {err}"

    # Re-check after prune
    new_pct = get_disk_pct()
    msg = (
        f"💾 <b>[j13-server] Disk Usage Alert: {pct:.1f}%</b>\n"
        f"Threshold: {DISK_THRESHOLD_PCT}%\n"
        f"🧹 docker system prune: {prune_result}\n"
        f"📊 Disk after prune: {new_pct:.1f}%\n"
        f"⏰ {_ts()}"
    )
    telegram.send(msg)
    daily_events.append(
        f"[{_ts()}] Disk {pct:.1f}% — {prune_result}, now {new_pct:.1f}%"
    )


def handle_ram_alert(pct: float) -> None:
    msg = (
        f"🧠 <b>[j13-server] RAM Usage Alert: {pct:.1f}%</b>\n"
        f"Threshold: {RAM_THRESHOLD_PCT}%\n"
        f"⏰ {_ts()}"
    )
    telegram.send(msg)
    daily_events.append(f"[{_ts()}] RAM {pct:.1f}% (threshold {RAM_THRESHOLD_PCT}%)")
    log.warning("RAM alert: %.1f%%", pct)


# ---------------------------------------------------------------------------
# Main monitor cycle
# ---------------------------------------------------------------------------

def monitor_cycle() -> None:
    """Single monitoring pass — called every CHECK_INTERVAL_MIN minutes."""
    log.info("--- monitor cycle start ---")

    # 1. Docker containers
    try:
        containers = get_containers()
        monitored = [
            c for c in containers
            if c.get("Names", "") not in SKIP_CONTAINERS
        ]
        for c in monitored:
            state = c.get("State", "").lower()
            if state == "exited":
                handle_exited_container(c)
    except Exception as e:
        log.error("Error during container check: %s", e)

    # 2. GPU temperature
    try:
        temp = get_gpu_temp()
        if temp is not None and temp > GPU_TEMP_THRESHOLD:
            handle_gpu_temp(temp)
        elif temp is not None:
            log.info("GPU temp: %d°C (OK)", temp)
    except Exception as e:
        log.error("Error during GPU check: %s", e)

    # 3. Disk usage
    try:
        disk_pct = get_disk_pct()
        log.info("Disk usage: %.1f%%", disk_pct)
        if disk_pct > DISK_THRESHOLD_PCT:
            handle_disk_alert(disk_pct)
    except Exception as e:
        log.error("Error during disk check: %s", e)

    # 4. RAM
    try:
        ram_pct = get_ram_pct()
        cpu_pct = get_cpu_pct()
        log.info("RAM: %.1f%%  CPU: %.1f%%", ram_pct, cpu_pct)
        if ram_pct > RAM_THRESHOLD_PCT:
            handle_ram_alert(ram_pct)
    except Exception as e:
        log.error("Error during RAM/CPU check: %s", e)

    log.info("--- monitor cycle end ---")


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

def send_daily_summary() -> None:
    global daily_events
    now = _ts()
    if daily_events:
        body = "\n".join(f"• {e}" for e in daily_events[-50:])  # cap at 50 lines
    else:
        body = "• No anomalies detected — all systems normal."

    containers = get_containers()
    running = sum(1 for c in containers if c.get("State", "").lower() == "running")
    total   = len(containers)

    msg = (
        f"📊 <b>[j13-server] Daily Summary</b>\n"
        f"🕘 {now}\n"
        f"🐳 Containers: {running}/{total} running\n\n"
        f"<b>Last 24h events:</b>\n{body}"
    )
    telegram.send(msg)
    log.info("Daily summary sent (%d events)", len(daily_events))
    daily_events = []  # reset after sending


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Startup notification
    containers = get_containers()
    n = len([c for c in containers if c.get("Names", "") not in SKIP_CONTAINERS])
    telegram.send(
        f"🟢 <b>ops-agent online</b> | monitoring {n} containers\n"
        f"⏰ {_ts()}"
    )
    log.info("ops-agent started. Monitoring %d containers every %d min.", n, CHECK_INTERVAL_MIN)

    # Schedule recurring tasks
    schedule.every(CHECK_INTERVAL_MIN).minutes.do(monitor_cycle)
    schedule.every().day.at("09:00").do(send_daily_summary)

    # Run first check immediately
    monitor_cycle()

    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except KeyboardInterrupt:
            log.info("ops-agent shutting down.")
            break
        except Exception as e:
            # Never let the outer loop crash
            log.error("Unexpected error in schedule loop: %s", e)
            time.sleep(30)


if __name__ == "__main__":
    main()
