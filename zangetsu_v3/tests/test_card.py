"""Tests for CardExporter artifact generation.

Verifies file creation, schema, checksum correctness, and journal schema.
No DB required — synthetic card_dict and dummy regime_model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from zangetsu_v3.cards.exporter import CardExporter, DEFAULT_JOURNAL_SCHEMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_JOURNAL_COLUMNS = [
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


def _make_card_dict() -> dict:
    """Synthetic card dict matching v3.0 schema (all required fields)."""
    return {
        "version": "3.0",
        "id": "test-card-001",
        "regime": "BULL_TREND",
        "warmup_bars": 50,
        "status": "PASSED_HOLDOUT",
        "created_at": "2026-04-04T00:00:00Z",
        "normalization": {
            "method": "robust_zscore",
            "medians": [0.0] * 15,
            "stds": [1.0] * 15,
        },
        "factors": [
            {"index": i, "name": f"factor_{i}", "ast": {"op": "ts_delta", "args": [{"col": "close"}, {"lit": 5}]}, "weight": 0.1}
            for i in range(15)
        ],
        "params": {
            "entry_threshold": 1.2,
            "exit_threshold": 0.5,
            "stop_atr_mult": 2.0,
            "position_frac": 0.1,
            "holding_bars_max": 120,
        },
        "cost_model": {"trading_bps": 3, "funding_rate_avg": 0.0001},
        "backtest": {
            "train_period": "2020-11 to 2025-06",
            "windows": [{"segment": i + 1, "sharpe": 1.5 + i * 0.1} for i in range(5)],
            "min_sharpe": 1.5,
            "sharpe_of_sharpes": 5.0,
            "symbols_tested": ["BTC"],
            "max_drawdown": 0.08,
            "trades_per_day": 12.5,
            "win_rate": 0.55,
            "return_skewness": -0.1,
            "return_kurtosis": 3.2,
        },
        "validation": {
            "method": "trimmed_min+DSR+holdout",
            "embargo_days": 90,
            "holdout_period": "2025-06 to 2026-03",
            "holdout_sharpe": 1.3,
            "holdout_max_drawdown": 0.09,
            "deflated_sharpe_ratio": 0.97,
            "total_candidates_tested": 5000,
        },
        "regime_labeler": {
            "model_path": "./regime_model.pkl",
            "n_regimes": 4,
            "lookback": 60,
            "debounce_bars": 5,
        },
        "deployment_hints": {
            "preferred_symbols": ["BTC", "ETH"],
            "max_concurrent_positions": 2,
        },
        "regime_includes": [0, 1],
        "applicable_symbols": ["BTC/USDT", "ETH/USDT"],
        "style": "hft",
    }


def _make_regime_model() -> dict:
    """Minimal regime model proxy (any picklable object)."""
    return {"n_states": 4, "type": "GaussianHMM", "stub": True}


@pytest.fixture()
def exporter() -> CardExporter:
    return CardExporter(version="3.0")


@pytest.fixture()
def exported_paths(tmp_path, exporter):
    card_dict = _make_card_dict()
    regime_model = _make_regime_model()
    paths = exporter.export(
        output_dir=tmp_path,
        card_payload=card_dict,
        regime_model=regime_model,
    )
    return paths, tmp_path


# ---------------------------------------------------------------------------
# File existence tests
# ---------------------------------------------------------------------------

class TestCardExporterFiles:
    def test_all_four_files_exist(self, exported_paths):
        paths, tmp_path = exported_paths
        assert (tmp_path / "card.json").exists()
        assert (tmp_path / "regime_model.pkl").exists()
        assert (tmp_path / "checksum.sha256").exists()
        assert (tmp_path / "live_journal.parquet").exists()

    def test_returned_paths_dict_has_all_keys(self, exported_paths):
        paths, _ = exported_paths
        assert set(paths.keys()) == {"card", "regime_model", "checksum", "journal"}

    def test_returned_paths_are_path_objects(self, exported_paths):
        paths, _ = exported_paths
        for key, p in paths.items():
            assert isinstance(p, Path), f"paths[{key!r}] is not a Path: {type(p)}"


# ---------------------------------------------------------------------------
# card.json content tests
# ---------------------------------------------------------------------------

class TestCardJson:
    def test_version_is_3_0(self, exported_paths):
        _, tmp_path = exported_paths
        with (tmp_path / "card.json").open() as f:
            data = json.load(f)
        assert data["version"] == "3.0"

    def test_card_id_preserved(self, exported_paths):
        _, tmp_path = exported_paths
        with (tmp_path / "card.json").open() as f:
            data = json.load(f)
        assert data["card_id"] == "test-card-001"

    def test_all_fields_preserved(self, exported_paths):
        _, tmp_path = exported_paths
        with (tmp_path / "card.json").open() as f:
            data = json.load(f)
        original = _make_card_dict()
        for key in original:
            # "id" is normalized to "card_id" on export
            check_key = "card_id" if key == "id" else key
            assert check_key in data, f"Missing key: {key} (as {check_key})"

    def test_json_is_valid_utf8(self, exported_paths):
        _, tmp_path = exported_paths
        raw = (tmp_path / "card.json").read_bytes()
        raw.decode("utf-8")  # should not raise

    def test_default_version_injected_when_missing(self, tmp_path, exporter):
        card_dict = _make_card_dict()
        del card_dict["version"]
        paths = exporter.export(
            output_dir=tmp_path / "no_version",
            card_payload=card_dict,
            regime_model=_make_regime_model(),
        )
        with paths["card"].open() as f:
            data = json.load(f)
        assert data["version"] == "3.0"


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_checksum_file_is_valid_sha256_hex(self, exported_paths):
        _, tmp_path = exported_paths
        checksum = (tmp_path / "checksum.sha256").read_text(encoding="utf-8").strip()
        assert len(checksum) == 64
        int(checksum, 16)  # raises if not valid hex

    def test_checksum_matches_card_plus_model_bytes(self, exported_paths):
        _, tmp_path = exported_paths
        recorded = (tmp_path / "checksum.sha256").read_text(encoding="utf-8").strip()

        sha = hashlib.sha256()
        sha.update((tmp_path / "card.json").read_bytes())
        sha.update((tmp_path / "regime_model.pkl").read_bytes())
        expected = sha.hexdigest()

        assert recorded == expected, (
            f"Checksum mismatch: recorded={recorded}, computed={expected}"
        )

    def test_checksum_changes_if_card_changes(self, tmp_path, exporter):
        card1 = _make_card_dict()
        card2 = dict(card1)
        card2["train_sharpe"] = 9.99

        out1 = tmp_path / "card1"
        out2 = tmp_path / "card2"
        paths1 = exporter.export(out1, card1, _make_regime_model())
        paths2 = exporter.export(out2, card2, _make_regime_model())

        cs1 = paths1["checksum"].read_text().strip()
        cs2 = paths2["checksum"].read_text().strip()
        assert cs1 != cs2


# ---------------------------------------------------------------------------
# live_journal.parquet tests
# ---------------------------------------------------------------------------

class TestLiveJournal:
    def test_journal_has_required_columns(self, exported_paths):
        _, tmp_path = exported_paths
        df = pl.read_parquet(tmp_path / "live_journal.parquet")
        for col in REQUIRED_JOURNAL_COLUMNS:
            assert col in df.columns, f"Missing journal column: {col}"

    def test_journal_columns_match_default_schema(self, exported_paths):
        _, tmp_path = exported_paths
        df = pl.read_parquet(tmp_path / "live_journal.parquet")
        assert set(df.columns) == set(DEFAULT_JOURNAL_SCHEMA)

    def test_empty_journal_has_zero_rows(self, exported_paths):
        _, tmp_path = exported_paths
        df = pl.read_parquet(tmp_path / "live_journal.parquet")
        assert len(df) == 0

    def test_custom_journal_data_preserved(self, tmp_path, exporter):
        """When a live_journal is provided, it's written as-is."""
        journal = pl.DataFrame(
            {col: [] for col in DEFAULT_JOURNAL_SCHEMA}
        ).with_columns(
            pl.lit(None).cast(pl.Utf8).alias("timestamp"),
        )
        # Provide one row of data
        journal_with_data = pl.DataFrame(
            {
                "timestamp": ["2026-04-04T00:00:00Z"],
                "symbol": ["BTC/USDT"],
                "side": ["buy"],
                "quantity": [0.1],
                "entry_price": [80000.0],
                "exit_price": [81000.0],
                "pnl": [100.0],
                "pnl_pct": [0.0125],
                "max_drawdown": [0.01],
                "regime_id": [2],
                "card_version": ["3.0"],
                "slippage_bps": [5.0],
                "funding": [0.001],
                "notes": ["test entry"],
            }
        )
        paths = exporter.export(
            output_dir=tmp_path / "with_journal",
            card_payload=_make_card_dict(),
            regime_model=_make_regime_model(),
            live_journal=journal_with_data,
        )
        loaded = pl.read_parquet(paths["journal"])
        assert len(loaded) == 1
        assert loaded["symbol"][0] == "BTC/USDT"

    def test_journal_is_readable_parquet(self, exported_paths):
        _, tmp_path = exported_paths
        df = pl.read_parquet(tmp_path / "live_journal.parquet")
        assert isinstance(df, pl.DataFrame)


# ---------------------------------------------------------------------------
# Output directory creation
# ---------------------------------------------------------------------------

class TestOutputDirectory:
    def test_creates_nested_output_dir(self, tmp_path, exporter):
        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()
        exporter.export(
            output_dir=nested,
            card_payload=_make_card_dict(),
            regime_model=_make_regime_model(),
        )
        assert nested.exists()
