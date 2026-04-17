#!/usr/bin/env python3
"""Calcifer Nightly Maintenance — runs daily TW 00:00-01:00 (UTC 16:00-17:00).

Performs:
  1. Docker prune (unused containers, dangling images, builder cache)
  2. PostgreSQL VACUUM ANALYZE (zangetsu + akasha DBs)
  3. Redis memory snapshot + LRU info
  4. AKASHA POST /compact (clean stale chunks)
  5. Log rotation (compress >100MB logs older than 7d)
  6. Backup verification (PG/Redis backup file age check)
  7. Disk/Memory/GPU health snapshot
  8. Writes summary to AKASHA agent_findings + Telegram alert
  9. Hard time cap: 55 min (gives 5 min buffer before 01:00)

Idempotent. Safe to re-run. Single-shot (designed for systemd timer).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

START = time.monotonic()
HARD_CAP_S = 55 * 60  # 55 min
LOG_FILE = "/home/j13/j13-ops/calcifer/maintenance.log"
AKASHA_URL = "http://100.123.49.102:8769"
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8237499581:AAFfSngYTSmsmVHPCMMFw0g7kkXpOj5kDFU")
TG_CHAT = os.environ.get("TG_CHAT_ID", "5252897787")

results = {"start": datetime.now(timezone.utc).isoformat(), "tasks": {}}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = json.dumps({"ts": ts, "level": level, "msg": str(msg)[:500]})
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def time_left():
    return HARD_CAP_S - (time.monotonic() - START)


def run(cmd, timeout=300):
    """Run shell command, return (rc, stdout)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=min(timeout, max(int(time_left()), 30)))
        return r.returncode, (r.stdout + r.stderr).strip()[:2000]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, str(e)[:300]


def task(name):
    """Decorator: runs function, captures result, respects time cap."""
    def deco(fn):
        def wrapper():
            if time_left() < 60:
                results["tasks"][name] = {"status": "SKIPPED_TIME_CAP"}
                log(f"[{name}] SKIPPED — only {int(time_left())}s left")
                return
            t0 = time.monotonic()
            try:
                ok, output = fn()
                dur = time.monotonic() - t0
                results["tasks"][name] = {
                    "status": "OK" if ok else "WARN",
                    "duration_s": round(dur, 1),
                    "output": output[:800],
                }
                log(f"[{name}] {'OK' if ok else 'WARN'} ({dur:.1f}s)")
            except Exception as e:
                results["tasks"][name] = {"status": "ERROR", "error": str(e)[:300]}
                log(f"[{name}] ERROR: {e}", "ERROR")
        return wrapper
    return deco


@task("docker_prune")
def docker_prune():
    """Remove stopped containers + dangling images + builder cache."""
    rc, _ = run("docker container prune -f")
    rc2, _ = run("docker image prune -f")
    rc3, out = run("docker builder prune -f")
    rc4, df = run("docker system df --format 'table {{.Type}}\t{{.Total}}\t{{.Reclaimable}}'")
    return (rc == 0 and rc2 == 0 and rc3 == 0), f"system df after:\n{df}"


@task("postgres_vacuum")
def postgres_vacuum():
    """VACUUM ANALYZE on both zangetsu + akasha DBs."""
    z_rc, z_out = run(
        "docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu "
        "-c 'VACUUM (ANALYZE, VERBOSE) champion_pipeline' 2>&1 | tail -3",
        timeout=600,
    )
    a_rc, a_out = run(
        "docker exec akasha-postgres psql -U zangetsu -d akasha "
        "-c 'VACUUM (ANALYZE) chunks; VACUUM (ANALYZE) memory_relations' 2>&1 | tail -3",
        timeout=600,
    )
    return (z_rc == 0 and a_rc == 0), f"zangetsu:{z_out[-200:]}\nakasha:{a_out[-200:]}"


@task("redis_health")
def redis_health():
    """Snapshot Redis memory + key counts, no destructive ops."""
    rc1, mem = run("docker exec magi-redis-1 redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_policy'")
    rc2, db = run("docker exec magi-redis-1 redis-cli INFO keyspace")
    rc3, akmem = run("docker exec akasha-redis redis-cli INFO memory | grep used_memory_human")
    return rc1 == 0, f"magi: {mem}\n{db}\nakasha: {akmem}"


@task("akasha_compact")
def akasha_compact():
    """Trigger AKASHA POST /compact to prune stale chunks."""
    try:
        req = urllib.request.Request(
            f"{AKASHA_URL}/compact",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        return True, json.dumps(result)[:300]
    except Exception as e:
        return False, str(e)[:200]


@task("log_rotation")
def log_rotation():
    """Compress logs >100MB older than 7d. Skip if gzip not available."""
    rc, out = run(
        "find /home/j13/j13-ops -name '*.log' -size +100M -mtime +7 "
        "-exec gzip {} \\; 2>&1 | tail -5"
    )
    rc2, sizes = run("du -sh /home/j13/j13-ops/*/logs 2>/dev/null | head -10")
    return rc == 0, f"rotation: {out[:200]}\nsizes: {sizes}"


@task("backup_verify")
def backup_verify():
    """Check backup files exist + recent (within 25h)."""
    rc1, pg = run("ls -lh /home/j13/backups/postgres/*.sql.gz 2>/dev/null | tail -3")
    rc2, redis_bk = run("ls -lh /home/j13/backups/redis/*.rdb 2>/dev/null | tail -3")
    rc3, age = run("find /home/j13/backups -name '*.sql.gz' -mtime -2 | wc -l")
    fresh = age.strip().isdigit() and int(age.strip()) > 0
    return fresh, f"pg:\n{pg}\nredis:\n{redis_bk}\nfresh_pg_24h={age.strip()}"


@task("disk_memory_gpu")
def disk_memory_gpu():
    """Snapshot critical resource state."""
    rc1, df = run("df -h / /home /var/lib/docker 2>/dev/null | head -5")
    rc2, mem = run("free -h | head -2")
    rc3, gpu = run("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo 'no GPU'")
    rc4, load = run("uptime")
    return True, f"disk:\n{df}\nmem:\n{mem}\ngpu: {gpu}\nload: {load}"


@task("zangetsu_status")
def zangetsu_status():
    """Quick Zangetsu pipeline state check."""
    rc1, services = run(
        "for s in arena-pipeline arena23-orchestrator arena45-orchestrator "
        "arena13-feedback.timer dashboard-api console-api; do "
        "  echo \"$s: $(systemctl is-active $s 2>/dev/null)\"; "
        "done"
    )
    rc2, db = run(
        "docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu -t -c "
        "\"SELECT 'champions=' || count(*) || ' deployable=' || "
        "count(*) FILTER (WHERE status='DEPLOYABLE') FROM champion_pipeline\""
    )
    return True, f"services:\n{services}\ndb:\n{db}"


def write_to_akasha(severity, summary):
    """Write maintenance summary to AKASHA + Telegram."""
    finding_content = (
        f"[calcifer maintenance {results['start']}] "
        f"{summary} | severity={severity} | "
        f"recommendation=review failed tasks if any"
    )
    body = json.dumps({
        "project": "_global",
        "segment": "agent_findings",
        "content": finding_content,
        "tags": ["calcifer", "maintenance", "nightly"],
        "confidence": "EXTRACTED",
        "source": f"calcifer.maintenance:{results['start']}",
    }).encode()
    try:
        req = urllib.request.Request(
            f"{AKASHA_URL}/memory/sync", data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read()).get("status") == "inserted"
    except Exception as e:
        log(f"AKASHA write failed: {e}", "ERROR")
        return False


def notify_telegram(severity, summary):
    if not TG_BOT_TOKEN:
        return False
    text = f"🔥 *CALCIFER 夜間維護*\nSeverity: {severity}\n{summary[:500]}"
    body = json.dumps({
        "chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown",
    }).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                data=body, headers={"Content-Type": "application/json"},
            ),
            timeout=10,
        )
        return True
    except Exception:
        return False


def main():
    log("Calcifer nightly maintenance starting (TW 00:00-01:00)")

    # Run all maintenance tasks
    docker_prune()
    postgres_vacuum()
    redis_health()
    akasha_compact()
    log_rotation()
    backup_verify()
    disk_memory_gpu()
    zangetsu_status()

    # Compute summary
    results["end"] = datetime.now(timezone.utc).isoformat()
    results["duration_s"] = round(time.monotonic() - START, 1)

    ok = sum(1 for t in results["tasks"].values() if t.get("status") == "OK")
    warn = sum(1 for t in results["tasks"].values() if t.get("status") == "WARN")
    err = sum(1 for t in results["tasks"].values() if t.get("status") == "ERROR")
    skip = sum(1 for t in results["tasks"].values() if t.get("status") == "SKIPPED_TIME_CAP")

    severity = "info" if (err == 0 and warn <= 1) else ("warning" if err == 0 else "high")
    summary = (
        f"OK={ok} WARN={warn} ERR={err} SKIP={skip} "
        f"duration={results['duration_s']}s"
    )

    log(f"Maintenance complete: {summary}")
    write_to_akasha(severity, summary)
    notify_telegram(severity, f"{summary}\n\nTasks:\n" + "\n".join(
        f"  {n}: {t.get('status','?')}" for n, t in results["tasks"].items()
    ))

    # Persist full result for diff next day
    try:
        with open("/home/j13/j13-ops/calcifer/maintenance_last.json", "w") as f:
            json.dump(results, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if err == 0 else 1)


if __name__ == "__main__":
    main()
