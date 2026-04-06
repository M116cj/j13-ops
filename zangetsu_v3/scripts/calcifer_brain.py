"""
Calcifer Brain — Status assessment and decision logic for Zangetsu V3.1 monitoring.

Categorizes system health into HEALTHY / WARNING / CRITICAL based on live data.
No Telegram I/O — pure logic module consumed by calcifer_bot.py.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import polars as pl


# ---------------------------------------------------------------------------
# Status categories
# ---------------------------------------------------------------------------

class Status(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def icon(self) -> str:
        return {
            Status.HEALTHY: "\U0001f49a",   # 💚
            Status.WARNING: "\U0001f7e1",   # 🟡
            Status.CRITICAL: "\U0001f534",  # 🔴
        }[self]

    @property
    def label(self) -> str:
        return f"{self.icon} {self.value}"


# ---------------------------------------------------------------------------
# Finding: a single health check result
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    category: str       # e.g. "data_freshness", "process", "risk"
    status: Status
    message: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Assessment: aggregate of all findings
# ---------------------------------------------------------------------------

@dataclass
class Assessment:
    overall: Status
    findings: list[Finding] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def summary_text(self) -> str:
        lines = [f"<b>{self.overall.label}</b>  ({self.timestamp})\n"]
        for f in self.findings:
            lines.append(f"  {f.status.icon} <b>{f.category}</b>: {f.message}")
            if f.detail:
                lines.append(f"      <i>{f.detail}</i>")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Thresholds (configurable via env)
# ---------------------------------------------------------------------------

STALE_WARN_S = int(os.getenv("CALCIFER_STALE_WARN_S", "30"))
STALE_CRIT_S = int(os.getenv("CALCIFER_STALE_CRIT_S", "60"))
LATENCY_WARN_MS = float(os.getenv("CALCIFER_LATENCY_WARN_MS", "30"))
LATENCY_CRIT_MS = float(os.getenv("CALCIFER_LATENCY_CRIT_MS", "50"))
WIN_RATE_WARN = float(os.getenv("CALCIFER_WIN_RATE_WARN", "0.40"))
REGIME_STUCK_BARS = int(os.getenv("CALCIFER_REGIME_STUCK_BARS", "500"))


# ---------------------------------------------------------------------------
# Brain: reads files, produces assessments
# ---------------------------------------------------------------------------

class CalciferBrain:
    """Stateless health assessor. Reads status.json + strategy dirs on each call."""

    def __init__(
        self,
        status_file: Path,
        strategies_dir: Path,
        arena_log_dir: Path,
    ) -> None:
        self.status_file = status_file
        self.strategies_dir = strategies_dir
        self.arena_log_dir = arena_log_dir

    # -- raw readers -------------------------------------------------------

    def _read_status(self) -> dict[str, Any]:
        if not self.status_file.exists():
            return {}
        try:
            return json.loads(self.status_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _discover_card_dirs(self) -> list[Path]:
        if not self.strategies_dir.exists():
            return []
        return sorted(
            d for d in self.strategies_dir.iterdir()
            if d.is_dir() and (d / "card.json").exists()
        )

    def _load_card(self, card_dir: Path) -> Optional[dict]:
        try:
            return json.loads((card_dir / "card.json").read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _read_journal(self, card_dir: Path) -> pl.DataFrame:
        jp = card_dir / "live_journal.parquet"
        if not jp.exists():
            return pl.DataFrame()
        try:
            return pl.read_parquet(jp)
        except Exception:
            return pl.DataFrame()

    def _today_utc_start(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    # -- individual checks -------------------------------------------------

    def _check_data_freshness(self, status: dict) -> Finding:
        last_bar = status.get("last_bar_time", "")
        if not last_bar:
            return Finding("data_freshness", Status.CRITICAL, "No bar time in status", "status.json missing or empty")

        try:
            ts = datetime.fromisoformat(last_bar.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
        except (ValueError, TypeError):
            return Finding("data_freshness", Status.CRITICAL, f"Unparseable bar time: {last_bar}")

        if age > STALE_CRIT_S:
            return Finding("data_freshness", Status.CRITICAL, f"Data stale {age:.0f}s", f"threshold {STALE_CRIT_S}s")
        if age > STALE_WARN_S:
            return Finding("data_freshness", Status.WARNING, f"Data aging {age:.0f}s", f"threshold {STALE_WARN_S}s")
        return Finding("data_freshness", Status.HEALTHY, f"Fresh ({age:.0f}s)")

    def _check_process(self, status: dict, tmux_session: str) -> Finding:
        if not status:
            return Finding("process", Status.CRITICAL, "status.json missing — process may be dead")

        import subprocess
        try:
            result = subprocess.run(
                f"tmux has-session -t {tmux_session} 2>/dev/null",
                shell=True, capture_output=True, timeout=5,
            )
            if result.returncode != 0:
                return Finding("process", Status.CRITICAL, f"tmux session '{tmux_session}' not found")
        except Exception as e:
            return Finding("process", Status.WARNING, f"Cannot check tmux: {e}")

        return Finding("process", Status.HEALTHY, "tmux session alive")

    def _check_risk(self, status: dict) -> Finding:
        net_exp = status.get("net_exposure", 0.0)
        gross_exp = status.get("gross_exposure", 0.0)
        max_gross = status.get("max_gross_exposure", 1.0)

        if gross_exp > max_gross:
            return Finding("risk", Status.CRITICAL, f"Gross exposure {gross_exp:.2f} > limit {max_gross:.2f}")
        if gross_exp > max_gross * 0.8:
            return Finding("risk", Status.WARNING, f"Gross exposure {gross_exp:.2f} near limit {max_gross:.2f}")
        return Finding("risk", Status.HEALTHY, f"Exposure net={net_exp:.2f} gross={gross_exp:.2f}")

    def _check_latency(self, status: dict) -> Finding:
        lat = status.get("last_latency_ms", 0.0)
        if lat > LATENCY_CRIT_MS:
            return Finding("latency", Status.CRITICAL, f"{lat:.1f}ms > {LATENCY_CRIT_MS}ms")
        if lat > LATENCY_WARN_MS:
            return Finding("latency", Status.WARNING, f"{lat:.1f}ms > {LATENCY_WARN_MS}ms")
        return Finding("latency", Status.HEALTHY, f"{lat:.1f}ms")

    def _check_regime(self, status: dict) -> Finding:
        regime = status.get("regime", "UNKNOWN")
        conf = status.get("confidence", 0.0)
        bars_in_regime = status.get("bars_in_regime", 0)

        if regime == "UNKNOWN":
            return Finding("regime", Status.WARNING, "Regime unknown")
        if bars_in_regime > REGIME_STUCK_BARS:
            return Finding("regime", Status.WARNING,
                           f"Regime {regime} for {bars_in_regime} bars",
                           f"stuck threshold {REGIME_STUCK_BARS}")
        return Finding("regime", Status.HEALTHY, f"{regime} ({conf:.0%}, {bars_in_regime} bars)")

    # -- aggregate assessments ---------------------------------------------

    def assess_health(self, tmux_session: str = "zangetsu") -> Assessment:
        """Full system health check."""
        status = self._read_status()
        findings = [
            self._check_data_freshness(status),
            self._check_process(status, tmux_session),
            self._check_risk(status),
            self._check_latency(status),
            self._check_regime(status),
        ]
        severity_order = {Status.HEALTHY: 0, Status.WARNING: 1, Status.CRITICAL: 2}
        worst = max(findings, key=lambda f: severity_order[f.status], default=None)
        overall = worst.status if worst else Status.HEALTHY
        return Assessment(overall=overall, findings=findings)

    def cards_summary(self) -> str:
        """Human-readable summary of all strategy cards."""
        dirs = self._discover_card_dirs()
        if not dirs:
            return "No strategy cards found."

        today_start = self._today_utc_start()
        lines = [f"<b>Strategy Cards ({len(dirs)})</b>\n<code>"]

        for cd in dirs:
            card = self._load_card(cd)
            card_id = card.get("id", cd.name) if card else cd.name
            card_status = card.get("status", "?") if card else "?"
            df = self._read_journal(cd)

            if df.is_empty() or "pnl_pct" not in df.columns:
                lines.append(f"  {card_id} [{card_status}]: no trades")
                continue

            pnl_col = df["pnl_pct"].drop_nulls()
            cum_pnl = float(pnl_col.sum()) if len(pnl_col) > 0 else 0.0
            n_trades = len(df)

            # Win rate
            wins = pnl_col.filter(pnl_col > 0).len()
            wr = wins / max(n_trades, 1)

            # Today PnL
            today_pnl = 0.0
            today_trades = 0
            if "timestamp" in df.columns:
                try:
                    tdf = df.filter(pl.col("timestamp") >= today_start)
                    today_pnl = float(tdf["pnl_pct"].drop_nulls().sum()) if len(tdf) > 0 else 0.0
                    today_trades = len(tdf)
                except Exception:
                    pass

            wr_icon = "\U0001f7e2" if wr >= 0.5 else ("\U0001f7e1" if wr >= WIN_RATE_WARN else "\U0001f534")
            lines.append(
                f"  {card_id} [{card_status}]\n"
                f"    cum={cum_pnl:+.4f} today={today_pnl:+.4f} "
                f"trades={n_trades} today={today_trades}\n"
                f"    WR={wr:.0%} {wr_icon}"
            )

        lines.append("</code>")
        return "\n".join(lines)

    def arena_summary(self) -> str:
        """Human-readable summary of arena search progress."""
        if not self.arena_log_dir.exists():
            return "No arena log directory found."

        log_files = sorted(self.arena_log_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            log_files = sorted(self.arena_log_dir.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)

        if not log_files:
            return "No arena logs found."

        lines = [f"<b>Arena Progress</b>\n<code>"]
        lines.append(f"Log files: {len(log_files)}")
        lines.append(f"Latest: {log_files[0].name}")

        # Try to read the latest log
        latest = log_files[0]
        try:
            if latest.suffix == ".json":
                data = json.loads(latest.read_text())
                if isinstance(data, dict):
                    gen = data.get("generation", "?")
                    best = data.get("best_fitness", "?")
                    pop = data.get("population_size", "?")
                    lines.append(f"Generation: {gen}")
                    lines.append(f"Best fitness: {best}")
                    lines.append(f"Population: {pop}")
                elif isinstance(data, list):
                    lines.append(f"Entries: {len(data)}")
            elif latest.suffix == ".parquet":
                df = pl.read_parquet(latest)
                lines.append(f"Rows: {len(df)}")
                if "fitness" in df.columns:
                    best = df["fitness"].max()
                    lines.append(f"Best fitness: {best}")
        except Exception as e:
            lines.append(f"(parse error: {e})")

        lines.append("</code>")
        return "\n".join(lines)

    def status_text(self) -> str:
        """Compact current-state text for /status command."""
        status = self._read_status()
        if not status:
            return "\U0001f534 <b>Status unavailable</b> — status.json missing or unreadable"

        regime = status.get("regime", "UNKNOWN")
        conf = status.get("confidence", 0.0)
        active = status.get("active_card_id", "–")
        stale = status.get("stale_status", "?")
        last_bar = status.get("last_bar_time", "–")
        net_exp = status.get("net_exposure", 0.0)
        gross_exp = status.get("gross_exposure", 0.0)
        open_pos = status.get("open_positions", 0)

        # Aggregate PnL
        today_start = self._today_utc_start()
        today_pnl = 0.0
        cum_pnl = 0.0
        card_count = 0
        for cd in self._discover_card_dirs():
            card_count += 1
            df = self._read_journal(cd)
            if df.is_empty() or "pnl_pct" not in df.columns:
                continue
            cum_pnl += float(df["pnl_pct"].drop_nulls().sum())
            if "timestamp" in df.columns:
                try:
                    tdf = df.filter(pl.col("timestamp") >= today_start)
                    today_pnl += float(tdf["pnl_pct"].drop_nulls().sum()) if len(tdf) > 0 else 0.0
                except Exception:
                    pass

        bar_display = last_bar[-8:] if len(last_bar) > 8 else last_bar

        return (
            f"<b>Zangetsu V3.1 Status</b>\n"
            f"<code>"
            f"Regime:   {regime} ({conf:.0%})\n"
            f"Active:   {active}\n"
            f"Data:     {stale} | bar {bar_display}\n"
            f"Today:    {today_pnl:+.4f}\n"
            f"Cum PnL:  {cum_pnl:+.4f}\n"
            f"Exposure: net {net_exp:.2f} / gross {gross_exp:.2f}\n"
            f"Cards:    {card_count} | Positions: {open_pos}"
            f"</code>"
        )


# ---------------------------------------------------------------------------
# Alert decision logic
# ---------------------------------------------------------------------------

@dataclass
class AlertDecision:
    should_alert: bool
    event_type: str
    severity: Status
    message: str


class AlertTracker:
    """Tracks alert state to avoid spam. Cooldown per event type."""

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self.cooldown = cooldown_seconds
        self._last_alert: dict[str, float] = {}

    def should_fire(self, event_type: str) -> bool:
        last = self._last_alert.get(event_type, 0.0)
        if time.time() - last < self.cooldown:
            return False
        return True

    def record(self, event_type: str) -> None:
        self._last_alert[event_type] = time.time()

    def evaluate_assessment(self, assessment: Assessment) -> list[AlertDecision]:
        """Given a health assessment, decide which alerts to fire."""
        decisions: list[AlertDecision] = []
        for f in assessment.findings:
            if f.status == Status.CRITICAL:
                event_type = f"CRITICAL_{f.category}"
                if self.should_fire(event_type):
                    decisions.append(AlertDecision(
                        should_alert=True,
                        event_type=event_type,
                        severity=Status.CRITICAL,
                        message=f"\U0001f534 <b>CRITICAL: {f.category}</b>\n{f.message}"
                        + (f"\n<i>{f.detail}</i>" if f.detail else ""),
                    ))
            elif f.status == Status.WARNING:
                event_type = f"WARNING_{f.category}"
                if self.should_fire(event_type):
                    decisions.append(AlertDecision(
                        should_alert=True,
                        event_type=event_type,
                        severity=Status.WARNING,
                        message=f"\U0001f7e1 <b>WARNING: {f.category}</b>\n{f.message}"
                        + (f"\n<i>{f.detail}</i>" if f.detail else ""),
                    ))
        return decisions


__all__ = [
    "Status", "Finding", "Assessment",
    "CalciferBrain", "AlertTracker", "AlertDecision",
]
