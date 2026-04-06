#!/usr/bin/env python3
"""Quarterly rolling holdout automation script.

Automates the quarterly data rotation cycle:
1. Old HOLDOUT segments → merge into TRAIN pool
2. New incoming data → embargo period (configurable)
3. Post-embargo data → new HOLDOUT
4. Trigger regime labeler re-run on new data
5. Trigger segment re-extraction
6. Archive old evaluation results

Usage:
    python scripts/rolling_holdout_auto.py --data-dir data/ --quarter 2026Q1
    python scripts/rolling_holdout_auto.py --data-dir data/ --quarter 2026Q1 --dry-run
    python scripts/rolling_holdout_auto.py --data-dir data/ --auto  # detect current quarter
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zangetsu_v3.core.data_split import DataSplit, SplitResult
from zangetsu_v3.core.segment_extractor import SegmentExtractor
from zangetsu_v3.regime.labeler import RegimeLabeler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RotationConfig:
    """All knobs for quarterly rotation."""

    embargo_days: int = 5
    holdout_months: int = 3
    min_holdout_segments: int = 3
    min_segment_bars: int = 1440  # 1 day of 1m bars
    archive_old_results: bool = True
    quarter: Optional[str] = None  # e.g. "2026Q1"
    auto_detect_quarter: bool = False
    dry_run: bool = False
    data_dir: Path = field(default_factory=lambda: Path("data"))
    archive_dir: Path = field(default_factory=lambda: Path("data/archive"))
    model_path: Optional[Path] = None  # path to existing regime model

    def current_quarter_label(self) -> str:
        if self.quarter:
            return self.quarter
        now = datetime.now(tz=__import__("datetime").timezone.utc)
        q = (now.month - 1) // 3 + 1
        return f"{now.year}Q{q}"


# ---------------------------------------------------------------------------
# Core rotation logic
# ---------------------------------------------------------------------------

class RollingHoldoutAutomation:
    """Orchestrates quarterly holdout rotation."""

    def __init__(self, config: RotationConfig):
        self.config = config
        self.splitter = DataSplit(
            embargo_days=config.embargo_days,
            holdout_months=config.holdout_months,
        )
        self.segment_extractor = SegmentExtractor(
            min_segment_bars=config.min_segment_bars,
        )
        self._actions_log: list[str] = []

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def run(
        self,
        train: pl.DataFrame,
        holdout: pl.DataFrame,
        new_data: pl.DataFrame,
        regime_labeler: Optional[RegimeLabeler] = None,
    ) -> RotationResult:
        """Execute the full rotation pipeline.

        Returns a RotationResult describing what happened (or would happen
        in dry-run mode).
        """
        quarter = self.config.current_quarter_label()
        self._log(f"Starting rotation for {quarter} (dry_run={self.config.dry_run})")

        # Step 1: Merge old holdout into train
        merged_train = self._merge_old_holdout_to_train(train, holdout)

        # Step 2: Apply embargo to new data
        new_data_sorted = new_data.sort("timestamp") if not new_data.is_empty() else new_data
        embargoable, post_embargo = self._apply_embargo(new_data_sorted)

        # Step 3: Re-split to form new train/embargo/holdout
        combined = pl.concat(
            [merged_train, embargoable, post_embargo],
            how="diagonal_relaxed",
        )
        if not combined.is_empty():
            combined = combined.sort("timestamp").unique(subset=["timestamp"], keep="last")

        new_train, new_embargo, new_holdout = self.splitter.split(combined)

        # Step 4: Validate holdout has enough segments
        holdout_segment_count = self._count_holdout_segments(
            new_holdout, regime_labeler
        )
        validation_passed = holdout_segment_count >= self.config.min_holdout_segments

        if not validation_passed:
            self._log(
                f"VALIDATION FAILED: new holdout has {holdout_segment_count} segments, "
                f"need >= {self.config.min_holdout_segments}"
            )

        # Step 5: Re-run regime labeler on new data (if provided and not dry-run)
        regime_labels = None
        if regime_labeler is not None and not new_holdout.is_empty():
            if self.config.dry_run:
                self._log("DRY-RUN: would re-run regime labeler on new holdout")
            else:
                self._log("Re-running regime labeler on new holdout data")
                regime_labels = regime_labeler.label(new_holdout)

        # Step 6: Re-extract segments (if not dry-run)
        segments = None
        if regime_labeler is not None and regime_labels is not None and not self.config.dry_run:
            self._log("Re-extracting segments from new holdout")
            segments = self.segment_extractor.extract_symbol(
                new_holdout, regime_labels, "combined"
            )

        # Step 7: Archive old results
        if self.config.archive_old_results:
            self._archive_old_results(quarter)

        result = RotationResult(
            quarter=quarter,
            dry_run=self.config.dry_run,
            old_train_rows=len(train),
            old_holdout_rows=len(holdout),
            new_data_rows=len(new_data),
            merged_train_rows=len(new_train),
            embargo_rows=len(new_embargo),
            new_holdout_rows=len(new_holdout),
            holdout_segment_count=holdout_segment_count,
            min_holdout_segments=self.config.min_holdout_segments,
            validation_passed=validation_passed,
            actions=list(self._actions_log),
            new_train=new_train,
            new_embargo=new_embargo,
            new_holdout=new_holdout,
        )
        return result

    # ---------------------------------------------------------------
    # Pipeline steps
    # ---------------------------------------------------------------

    def _merge_old_holdout_to_train(
        self, train: pl.DataFrame, holdout: pl.DataFrame
    ) -> pl.DataFrame:
        """Step 1: old HOLDOUT → TRAIN pool."""
        if holdout.is_empty():
            self._log("No old holdout to merge")
            return train
        self._log(f"Merging {len(holdout)} old holdout rows into train ({len(train)} rows)")
        merged = pl.concat([train, holdout], how="diagonal_relaxed")
        if not merged.is_empty():
            merged = merged.sort("timestamp").unique(subset=["timestamp"], keep="last")
        return merged

    def _apply_embargo(
        self, new_data: pl.DataFrame
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Step 2: split new_data into embargo and post-embargo portions.

        Returns (embargo_portion, post_embargo_portion).
        """
        if new_data.is_empty():
            self._log("No new data for embargo split")
            return new_data, new_data

        embargo_delta = timedelta(days=self.config.embargo_days)
        first_ts = new_data[0, "timestamp"]
        embargo_end = first_ts + embargo_delta

        ts = pl.col("timestamp")
        embargo_portion = new_data.filter(ts < embargo_end)
        post_embargo = new_data.filter(ts >= embargo_end)

        self._log(
            f"Embargo split: {len(embargo_portion)} rows in embargo "
            f"({self.config.embargo_days} days), {len(post_embargo)} rows post-embargo"
        )
        return embargo_portion, post_embargo

    def _count_holdout_segments(
        self, holdout: pl.DataFrame, labeler: Optional[RegimeLabeler]
    ) -> int:
        """Count segments in the new holdout for validation."""
        if holdout.is_empty():
            return 0

        if labeler is not None:
            try:
                labels = labeler.label(holdout)
                segments = self.segment_extractor.extract_symbol(
                    holdout, labels, "validation"
                )
                count = len(segments)
                self._log(f"Holdout segment count (via labeler): {count}")
                return count
            except Exception as e:
                self._log(f"Labeler failed during validation: {e}")

        # Fallback: estimate segments by time gaps (> 1 day gap = new segment)
        if "timestamp" not in holdout.columns:
            return 0
        ts = holdout["timestamp"].sort()
        if len(ts) < 2:
            return 1 if len(ts) > 0 else 0
        diffs = ts.diff().drop_nulls()
        gap_threshold = timedelta(days=1)
        n_gaps = (diffs > gap_threshold).sum()
        count = int(n_gaps) + 1
        self._log(f"Holdout segment count (time-gap heuristic): {count}")
        return count

    def _archive_old_results(self, quarter: str) -> None:
        """Step 6: archive old evaluation results."""
        archive_dir = self.config.archive_dir / quarter
        if self.config.dry_run:
            self._log(f"DRY-RUN: would archive old results to {archive_dir}")
            return

        results_dir = self.config.data_dir / "results"
        if not results_dir.exists():
            self._log("No results directory to archive")
            return

        archive_dir.mkdir(parents=True, exist_ok=True)
        for f in results_dir.iterdir():
            if f.is_file():
                dest = archive_dir / f.name
                shutil.copy2(f, dest)
                self._log(f"Archived {f.name} → {archive_dir}")
        self._log(f"Archived old results to {archive_dir}")

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self._actions_log.append(msg)
        logger.info(msg)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RotationResult:
    quarter: str
    dry_run: bool
    old_train_rows: int
    old_holdout_rows: int
    new_data_rows: int
    merged_train_rows: int
    embargo_rows: int
    new_holdout_rows: int
    holdout_segment_count: int
    min_holdout_segments: int
    validation_passed: bool
    actions: list[str]
    new_train: pl.DataFrame
    new_embargo: pl.DataFrame
    new_holdout: pl.DataFrame

    def summary(self) -> str:
        status = "PASS" if self.validation_passed else "FAIL"
        mode = "DRY-RUN" if self.dry_run else "EXECUTED"
        lines = [
            f"=== Rolling Holdout Rotation [{mode}] — {self.quarter} ===",
            f"Old train:     {self.old_train_rows:>8} rows",
            f"Old holdout:   {self.old_holdout_rows:>8} rows",
            f"New data:      {self.new_data_rows:>8} rows",
            f"---",
            f"New train:     {self.merged_train_rows:>8} rows",
            f"Embargo:       {self.embargo_rows:>8} rows",
            f"New holdout:   {self.new_holdout_rows:>8} rows",
            f"---",
            f"Holdout segments: {self.holdout_segment_count} (min required: {self.min_holdout_segments})",
            f"Validation: {status}",
            f"---",
            "Actions:",
        ]
        for a in self.actions:
            lines.append(f"  • {a}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Quarterly rolling holdout rotation automation"
    )
    p.add_argument("--data-dir", type=Path, default=Path("data"), help="Data directory")
    p.add_argument("--quarter", type=str, default=None, help="Quarter label, e.g. 2026Q1")
    p.add_argument("--auto", action="store_true", help="Auto-detect current quarter")
    p.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    p.add_argument("--embargo-days", type=int, default=5, help="Embargo period in days")
    p.add_argument("--holdout-months", type=int, default=3, help="Holdout window in months")
    p.add_argument("--min-segments", type=int, default=3, help="Min holdout segments")
    p.add_argument("--min-segment-bars", type=int, default=1440, help="Min bars per segment")
    p.add_argument("--model-path", type=Path, default=None, help="Path to regime model")
    p.add_argument("--no-archive", action="store_true", help="Skip archiving old results")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = RotationConfig(
        embargo_days=args.embargo_days,
        holdout_months=args.holdout_months,
        min_holdout_segments=args.min_segments,
        min_segment_bars=args.min_segment_bars,
        archive_old_results=not args.no_archive,
        quarter=args.quarter,
        auto_detect_quarter=args.auto,
        dry_run=args.dry_run,
        data_dir=args.data_dir,
        archive_dir=args.data_dir / "archive",
        model_path=args.model_path,
    )

    if not config.quarter and not config.auto_detect_quarter:
        logger.error("Specify --quarter or --auto")
        return 1

    # Load data files
    train_path = config.data_dir / "train.parquet"
    holdout_path = config.data_dir / "holdout.parquet"
    new_data_path = config.data_dir / "new_data.parquet"

    for p in [train_path, holdout_path, new_data_path]:
        if not p.exists():
            logger.error(f"Missing data file: {p}")
            return 1

    train = pl.read_parquet(train_path)
    holdout = pl.read_parquet(holdout_path)
    new_data = pl.read_parquet(new_data_path)

    # Load regime model if provided
    labeler = None
    if config.model_path and config.model_path.exists():
        labeler = RegimeLabeler.load(config.model_path)

    automation = RollingHoldoutAutomation(config)
    result = automation.run(train, holdout, new_data, labeler)

    print(result.summary())

    if not result.validation_passed:
        logger.warning("Holdout validation FAILED — review before proceeding")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "RotationConfig",
    "RotationResult",
    "RollingHoldoutAutomation",
]
