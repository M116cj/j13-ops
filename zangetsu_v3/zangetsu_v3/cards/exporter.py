"""Export strategy card artifacts (card.json, regime model, checksum, journal)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import polars as pl


DEFAULT_JOURNAL_SCHEMA = [
    "timestamp",
    "symbol",
    "side",
    "quantity",
    "entry_price",
    "exit_price",
    "pnl",
    "pnl_pct",
    "max_drawdown",
    "regime_id",
    "card_version",
    "slippage_bps",
    "funding",
    "notes",
]


REQUIRED_CARD_FIELDS = {
    "version", "id", "regime", "warmup_bars",  # C26: warmup_bars mandatory
    "normalization", "factors", "params", "cost_model",
    "backtest", "validation", "regime_labeler", "deployment_hints",
    "status",  # RISK-3 fix: status must be PASSED_HOLDOUT or FAILED_HOLDOUT
    "regime_includes",  # V3.1: which regime IDs this card is trained on
    "applicable_symbols",  # V3.1: symbols this card applies to
    "style",  # V3.1: card trading style tag (e.g. "hft", "swing")
}


@dataclass
class CardExporter:
    version: str = "3.1"

    def export(
        self,
        output_dir: str | Path,
        card_payload: Dict[str, Any],
        regime_model: Any,
        live_journal: Optional[pl.DataFrame] = None,
    ) -> Dict[str, Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        card_payload = dict(card_payload)
        card_payload.setdefault("version", self.version)

        # C26 + RISK-3: validate required fields before writing
        missing = REQUIRED_CARD_FIELDS - set(card_payload.keys())
        if missing:
            raise ValueError(
                f"card_payload missing required fields: {sorted(missing)}. "
                "Ensure warmup_bars, status, regime_includes, applicable_symbols, "
                "and style are set."
            )

        # Normalize id → card_id in output JSON
        if "id" in card_payload and "card_id" not in card_payload:
            card_payload["card_id"] = card_payload.pop("id")

        card_path = out / "card.json"
        regime_path = out / "regime_model.pkl"
        checksum_path = out / "checksum.sha256"
        journal_path = out / "live_journal.parquet"

        with card_path.open("w", encoding="utf-8") as f:
            json.dump(card_payload, f, indent=2, sort_keys=True)

        joblib.dump(regime_model, regime_path)

        if live_journal is None:
            empty = {name: [] for name in DEFAULT_JOURNAL_SCHEMA}
            live_journal = pl.DataFrame(empty)
        live_journal.write_parquet(journal_path)

        sha = hashlib.sha256()
        sha.update(card_path.read_bytes())
        sha.update(regime_path.read_bytes())
        checksum_path.write_text(sha.hexdigest(), encoding="utf-8")

        return {
            "card": card_path,
            "regime_model": regime_path,
            "checksum": checksum_path,
            "journal": journal_path,
        }


__all__ = ["CardExporter", "DEFAULT_JOURNAL_SCHEMA"]
