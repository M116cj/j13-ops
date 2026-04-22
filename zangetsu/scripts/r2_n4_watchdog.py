#!/usr/bin/env python3
"""R2-N4 Observation Window Watchdog — Alpha OS 2.0 / Recovery Program v1.

Runs 2 hours (7200 s) starting at R2N3_T0 = 2026-04-22T17:56:47Z.
Deadline: 2026-04-22T19:56:47Z.

Poll cadence:
  - every  5 min: check 3 alert conditions (fire Telegram on transition, never spam)
  - every 10 min: JSON snapshot appended to observation log
  - at T+120 min: final summary + self-exit

Alert conditions (NO auto-revert; alert only, then wait for j13):
  [A] T+120min stall:  deployable_count still 0 AND last_live_at_age_h still NULL → CRITICAL
  [B] A2 pass>30%:     a2_pass_rate = ARENA2_COMPLETE / (ARENA2_COMPLETE+ARENA2_REJECTED)
                       computed over rows with updated_at >= R2N3_T0. Alert if > 0.30 (noise-fitting).
  [C] few_trades>90%:  within last-5-min A1 rejects counters, few_trades/(all_reject) > 0.90
                       (data starvation).

Each alert only fires ONCE per condition per process lifetime (idempotent).

Observation log: /home/j13/claude-inbox/retros/zangetsu-recovery-program-v1/phase2/R2-N4-observation-log.jsonl
Each line = one JSON snapshot with full metrics.
"""
from __future__ import annotations
import json, subprocess, sys, time, os, re
from datetime import datetime, timezone
from pathlib import Path

# Pin calcifer notifier path (shared telegram infra)
sys.path.insert(0, "/home/j13/j13-ops/calcifer")
try:
    from notifier import notify_telegram
except Exception as e:
    def notify_telegram(agent_name, finding):
        print(f"[notifier missing: {e}] would-send: {agent_name} {finding}", flush=True)
        return False

R2N3_T0_EPOCH = 1776880607  # 2026-04-22T17:56:47Z
DEADLINE_EPOCH = R2N3_T0_EPOCH + 7200  # +2h
POLL_INTERVAL_S = 300  # 5 min
SNAPSHOT_EVERY = 2  # every 2 polls = 10 min

OBS_LOG = Path("/home/j13/claude-inbox/retros/zangetsu-recovery-program-v1/phase2/R2-N4-observation-log.jsonl")
ENGINE_LOG = Path("/home/j13/j13-ops/zangetsu/logs/engine.jsonl")

# State (fires-once gates)
FIRED = {"stall_2h": False, "a2_pass_gt_30": False, "few_trades_gt_90": False}

PSQL_CMD = [
    "docker", "exec", "-i", "deploy-postgres-1",
    "psql", "-U", "zangetsu", "-d", "zangetsu",
    "-At", "-F", "|", "-c",
]


def psql(sql: str) -> list[list[str]]:
    try:
        r = subprocess.run(PSQL_CMD + [sql], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return [["ERROR", r.stderr.strip()[:200]]]
        return [row.split("|") for row in r.stdout.strip().split("\n") if row]
    except Exception as e:
        return [["ERROR", str(e)[:200]]]


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_status_view() -> dict:
    rows = psql(
        "SELECT deployable_count, deployable_fresh, active_count, candidate_count, "
        "champions_last_1h, last_live_at_age_h FROM zangetsu_status;"
    )
    if not rows or rows[0][0] == "ERROR":
        return {"error": rows[0][1] if rows else "no_rows"}
    r = rows[0]
    return {
        "deployable_count": int(r[0]) if r[0] else 0,
        "deployable_fresh": int(r[1]) if r[1] else 0,
        "active_count": int(r[2]) if r[2] else 0,
        "candidate_count": int(r[3]) if r[3] else 0,
        "champions_last_1h": int(r[4]) if r[4] else 0,
        "last_live_at_age_h": float(r[5]) if r[5] and r[5] != "" else None,
    }


def read_fresh_status_hist() -> dict:
    rows = psql(
        "SELECT status, COUNT(*) FROM champion_pipeline_fresh GROUP BY status ORDER BY 2 DESC;"
    )
    if not rows or (rows[0][0] == "ERROR"):
        return {}
    return {r[0]: int(r[1]) for r in rows if len(r) >= 2 and r[1].isdigit()}


def read_a2_activity_since_t0() -> dict:
    """Fresh-table rows updated at-or-after R2N3_T0 and their status histogram.

    Covers the 89 re-enqueue plus any new alpha flowing through.
    """
    iso_t0 = datetime.fromtimestamp(R2N3_T0_EPOCH, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S+00"
    )
    rows = psql(
        f"SELECT status, COUNT(*) FROM champion_pipeline_fresh "
        f"WHERE updated_at >= '{iso_t0}' GROUP BY status;"
    )
    if not rows or rows[0][0] == "ERROR":
        return {}
    return {r[0]: int(r[1]) for r in rows if len(r) >= 2 and r[1].isdigit()}


def read_recent_a1_rejects(tail_bytes: int = 200_000) -> dict:
    """Parse last N bytes of engine.jsonl for A1 round-log reject counters.

    The patch emits: 'rejects: few_trades=X val_few=Y val_neg_pnl=Z val_sharpe=W val_wr=V'
    """
    if not ENGINE_LOG.exists():
        return {"error": "engine.jsonl missing"}
    try:
        size = ENGINE_LOG.stat().st_size
        with open(ENGINE_LOG, "rb") as f:
            f.seek(max(0, size - tail_bytes))
            data = f.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"error": str(e)[:100]}

    # Accumulate the LAST reject stats line (each round overrides — cumulative per-worker)
    pat = re.compile(
        r"rejects:\s*few_trades=(\d+)\s+val_few=(\d+)\s+val_neg_pnl=(\d+)\s+"
        r"val_sharpe=(\d+)\s+val_wr=(\d+)"
    )
    ms = pat.findall(data)
    if not ms:
        return {"n_rejects_lines": 0}
    # Use latest line (most recent round)
    ft, vf, vn, vs, vw = map(int, ms[-1])
    total = ft + vf + vn + vs + vw
    return {
        "n_rejects_lines": len(ms),
        "latest_few_trades": ft,
        "latest_val_few": vf,
        "latest_val_neg_pnl": vn,
        "latest_val_sharpe": vs,
        "latest_val_wr": vw,
        "latest_total_rejects": total,
        "few_trades_ratio": (ft / total) if total > 0 else 0.0,
    }


def read_a2_reject_reasons(tail_bytes: int = 300_000) -> dict:
    """Tail engine.jsonl for 'A2 REJECTED ... [V10]: X' reason distribution."""
    if not ENGINE_LOG.exists():
        return {}
    try:
        size = ENGINE_LOG.stat().st_size
        with open(ENGINE_LOG, "rb") as f:
            f.seek(max(0, size - tail_bytes))
            data = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return {}
    reasons = re.findall(r"A2 REJECTED[^\"]*\[V10\]:\s*([^\"\\\n]+)", data)
    hist: dict = {}
    for r in reasons[-500:]:  # last 500 only
        key = re.split(r"[=\s]", r.strip())[0]
        hist[key] = hist.get(key, 0) + 1
    return hist


def compute_a2_pass_rate(a2_activity: dict) -> tuple[float, int, int]:
    passed = a2_activity.get("ARENA2_COMPLETE", 0)
    failed = a2_activity.get("ARENA2_REJECTED", 0)
    total = passed + failed
    return (passed / total if total else 0.0, passed, total)


def try_alert(gate: str, agent: str, severity: str, insight: str, recommendation: str):
    if FIRED.get(gate):
        return None
    ok = notify_telegram(agent, {
        "severity": severity, "insight": insight, "recommendation": recommendation,
    })
    FIRED[gate] = True
    return ok


def main():
    OBS_LOG.parent.mkdir(parents=True, exist_ok=True)
    poll_count = 0
    print(f"[watchdog] start ts={iso_now()} deadline={datetime.fromtimestamp(DEADLINE_EPOCH, tz=timezone.utc).isoformat()}", flush=True)

    while True:
        now = int(time.time())
        t_plus_min = (now - R2N3_T0_EPOCH) / 60.0
        deadline_in = DEADLINE_EPOCH - now
        poll_count += 1

        status = read_status_view()
        fresh_hist = read_fresh_status_hist()
        a2_since = read_a2_activity_since_t0()
        a1_rejects = read_recent_a1_rejects()
        a2_reasons = read_a2_reject_reasons()
        a2_rate, a2_pass, a2_total = compute_a2_pass_rate(a2_since)

        snapshot = {
            "ts": iso_now(),
            "t_plus_min": round(t_plus_min, 2),
            "poll_n": poll_count,
            "status_view": status,
            "fresh_hist": fresh_hist,
            "a2_activity_since_t0": a2_since,
            "a2_pass_rate": round(a2_rate, 4),
            "a2_pass_count": a2_pass,
            "a2_total_since_t0": a2_total,
            "a1_rejects_latest": a1_rejects,
            "a2_reject_reasons_last500": a2_reasons,
        }

        # Snapshot log every 2 polls (10 min)
        if poll_count == 1 or poll_count % SNAPSHOT_EVERY == 0:
            with open(OBS_LOG, "a") as f:
                f.write(json.dumps(snapshot) + "\n")

        # Alert B: A2 pass rate > 30%
        if a2_rate > 0.30 and a2_total >= 10:
            try_alert(
                "a2_pass_gt_30", "R2N4",
                "warning",
                f"R2-N4 alert [B]: A2 pass rate {a2_rate:.1%} on {a2_total} rows since R2N3_T0 "
                f"(passed={a2_pass}). Exceeds 30% noise-fitting threshold. "
                f"Fresh hist: {fresh_hist}",
                "Pause R2-N3 expansion. Inspect passed alphas for OOS leak or holdout window variance. "
                "Possible fake recovery — verify against larger holdout or different regime."
            )

        # Alert C: few_trades > 90% of A1 rejects
        if a1_rejects.get("latest_total_rejects", 0) >= 1000:
            ftr = a1_rejects.get("few_trades_ratio", 0.0)
            if ftr > 0.90:
                try_alert(
                    "few_trades_gt_90", "R2N4",
                    "warning",
                    f"R2-N4 alert [C]: A1 few_trades reject ratio {ftr:.1%} at T+{t_plus_min:.0f}min. "
                    f"Counters: {a1_rejects}",
                    "Holdout/cost combination may be too narrow for base signal rate. "
                    "Investigate: (a) lower ENTRY_THR further, or (b) widen train_split so holdout has more bars, "
                    "or (c) drop per-pair min-trades gate."
                )

        # Alert A: 2h stall — at deadline (±1 poll)
        if deadline_in <= POLL_INTERVAL_S:
            dc = status.get("deployable_count", 0) if "error" not in status else -1
            age = status.get("last_live_at_age_h", None)
            if dc == 0 and (age is None):
                try_alert(
                    "stall_2h", "R2N4",
                    "critical",
                    f"R2-N4 alert [A]: 2h post-R2N3 stall. deployable_count=0 last_live=null. "
                    f"Fresh hist={fresh_hist}. A2 since R2N3_T0: {a2_since} (pass_rate={a2_rate:.2%}). "
                    f"A1 rejects latest: {a1_rejects}. A2 reject reasons: {a2_reasons}.",
                    "Flow-unblock did NOT produce deployable alpha in 2h. j13 decision required: "
                    "(1) extend observation window, (2) trigger Phase D0/D1 (target gate re-design), "
                    "or (3) rollback R2-N2 and try alternative hotfix. NO auto-revert per charter."
                )
            else:
                # Report status even if not stalled
                print(f"[watchdog] T+120min reached. No stall alert: dc={dc} age={age}", flush=True)

        # Periodic stdout for human tail
        print(f"[watchdog] T+{t_plus_min:5.1f}min poll#{poll_count} dc={status.get('deployable_count')} "
              f"fresh={fresh_hist} a2_since_t0={a2_since} a2_pass_rate={a2_rate:.2%} "
              f"a1_few_trades_ratio={a1_rejects.get('few_trades_ratio', 0):.3f} "
              f"a2_reasons={a2_reasons}", flush=True)

        # Exit at deadline
        if now >= DEADLINE_EPOCH:
            print(f"[watchdog] deadline reached at {iso_now()}. Final fired gates: {FIRED}", flush=True)
            # Write final snapshot with closure marker
            final = dict(snapshot)
            final["closure"] = {"reason": "deadline", "fired": dict(FIRED)}
            with open(OBS_LOG, "a") as f:
                f.write(json.dumps(final) + "\n")
            break

        # Sleep until next poll or deadline (whichever first)
        sleep_for = min(POLL_INTERVAL_S, max(1, DEADLINE_EPOCH - now))
        time.sleep(sleep_for)

    return 0


if __name__ == "__main__":
    sys.exit(main())
