"""Tests for scripts/arena_endpoints.py — Arena pipeline status endpoint."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_env(tmp_path, monkeypatch):
    """Point all arena paths to temp directories."""
    arena1_dir = tmp_path / "arena1_results"
    arena1_dir.mkdir()
    factor_pool = tmp_path / "factor_pool.json"
    arena3_dir = tmp_path / "arena3_checkpoints"
    arena3_dir.mkdir()

    monkeypatch.setenv("ZV3_ARENA1_RESULTS_DIR", str(arena1_dir))
    monkeypatch.setenv("ZV3_FACTOR_POOL_PATH", str(factor_pool))
    monkeypatch.setenv("ZV3_ARENA3_CHECKPOINT_DIR", str(arena3_dir))

    # Force module-level Path objects to re-resolve from env
    import scripts.arena_endpoints as mod
    monkeypatch.setattr(mod, "ARENA1_RESULTS_DIR", arena1_dir)
    monkeypatch.setattr(mod, "FACTOR_POOL_PATH", factor_pool)
    monkeypatch.setattr(mod, "ARENA3_CHECKPOINT_DIR", arena3_dir)


@pytest.fixture
def client():
    from scripts.arena_endpoints import arena_router
    app = FastAPI()
    app.include_router(arena_router)
    return TestClient(app)


@pytest.fixture
def arena1_dir(tmp_path):
    return tmp_path / "arena1_results"


@pytest.fixture
def factor_pool_path(tmp_path):
    return tmp_path / "factor_pool.json"


@pytest.fixture
def arena3_dir(tmp_path):
    return tmp_path / "arena3_checkpoints"


# ---------------------------------------------------------------------------
# Arena 1 tests
# ---------------------------------------------------------------------------


class TestArena1:
    def test_empty_returns_not_started(self, client):
        resp = client.get("/api/arena")
        assert resp.status_code == 200
        a1 = resp.json()["arena1"]
        assert a1["status"] == "not_started"
        assert a1["completed_runs"] == 0
        assert a1["total_runs"] == 55

    def test_partial_runs_returns_running(self, client, arena1_dir):
        for name in ["BULL_TREND_h1", "BEAR_TREND_h1", "RANGE_BOUND_h1"]:
            (arena1_dir / f"{name}.json").write_text(json.dumps([{"score": 0.5}]))
        resp = client.get("/api/arena")
        a1 = resp.json()["arena1"]
        assert a1["status"] == "running"
        assert a1["completed_runs"] == 3
        assert a1["latest_run"] != ""

    def test_55_runs_returns_completed(self, client, arena1_dir):
        for i in range(55):
            (arena1_dir / f"run_{i:03d}.json").write_text("[]")
        resp = client.get("/api/arena")
        a1 = resp.json()["arena1"]
        assert a1["status"] == "completed"
        assert a1["completed_runs"] == 55

    def test_latest_run_is_most_recent(self, client, arena1_dir):
        (arena1_dir / "OLD_RUN.json").write_text("[]")
        time.sleep(0.05)  # ensure different mtime
        (arena1_dir / "NEW_RUN.json").write_text("[]")
        resp = client.get("/api/arena")
        a1 = resp.json()["arena1"]
        assert a1["latest_run"] == "NEW_RUN"
        assert a1["latest_time"] != ""

    def test_nonexistent_dir(self, client, monkeypatch):
        import scripts.arena_endpoints as mod
        monkeypatch.setattr(mod, "ARENA1_RESULTS_DIR", Path("/tmp/nonexistent_xyz"))
        resp = client.get("/api/arena")
        a1 = resp.json()["arena1"]
        assert a1["status"] == "not_started"
        assert a1["completed_runs"] == 0


# ---------------------------------------------------------------------------
# Arena 2 tests
# ---------------------------------------------------------------------------


class TestArena2:
    def test_no_factor_pool_returns_not_started(self, client):
        resp = client.get("/api/arena")
        a2 = resp.json()["arena2"]
        assert a2["status"] == "not_started"
        assert a2["factor_count"] == 0

    def test_factor_pool_list_format(self, client, factor_pool_path):
        factors = [{"name": f"factor_{i}"} for i in range(12)]
        factor_pool_path.write_text(json.dumps(factors))
        resp = client.get("/api/arena")
        a2 = resp.json()["arena2"]
        assert a2["status"] == "completed"
        assert a2["factor_count"] == 12

    def test_factor_pool_dict_format(self, client, factor_pool_path):
        data = {"factors": [{"name": "f1"}, {"name": "f2"}]}
        factor_pool_path.write_text(json.dumps(data))
        resp = client.get("/api/arena")
        a2 = resp.json()["arena2"]
        assert a2["status"] == "completed"
        assert a2["factor_count"] == 2

    def test_corrupt_factor_pool(self, client, factor_pool_path):
        factor_pool_path.write_text("NOT JSON{{{")
        resp = client.get("/api/arena")
        a2 = resp.json()["arena2"]
        assert a2["status"] == "not_started"
        assert a2["factor_count"] == 0


# ---------------------------------------------------------------------------
# Arena 3 tests
# ---------------------------------------------------------------------------


class TestArena3:
    def test_no_checkpoints_returns_not_started(self, client):
        resp = client.get("/api/arena")
        a3 = resp.json()["arena3"]
        assert a3["status"] == "not_started"
        assert len(a3["regimes"]) == 5
        assert all(r["status"] == "pending" for r in a3["regimes"])

    def test_running_regime(self, client, arena3_dir):
        cp = {"generation": 15, "qd_score": 42.5, "elites": 30, "completed": False}
        (arena3_dir / "BULL_TREND.json").write_text(json.dumps(cp))
        resp = client.get("/api/arena")
        a3 = resp.json()["arena3"]
        assert a3["status"] == "running"
        bull = next(r for r in a3["regimes"] if r["name"] == "BULL_TREND")
        assert bull["status"] == "running"
        assert bull["gen"] == 15
        assert bull["qd_score"] == 42.5
        assert bull["elites"] == 30

    def test_all_completed(self, client, arena3_dir):
        for regime in ["BULL_TREND", "BEAR_TREND", "RANGE_BOUND", "HIGH_VOL", "LOW_VOL"]:
            cp = {"generation": 50, "qd_score": 100.0, "elites": 80, "completed": True}
            (arena3_dir / f"{regime}.json").write_text(json.dumps(cp))
        resp = client.get("/api/arena")
        a3 = resp.json()["arena3"]
        assert a3["status"] == "completed"

    def test_mixed_regimes(self, client, arena3_dir):
        # One completed, one running, rest pending
        (arena3_dir / "BULL_TREND.json").write_text(
            json.dumps({"generation": 50, "completed": True, "qd_score": 90, "elites": 70})
        )
        (arena3_dir / "BEAR_TREND.json").write_text(
            json.dumps({"generation": 10, "completed": False, "qd_score": 20, "elites": 5})
        )
        resp = client.get("/api/arena")
        a3 = resp.json()["arena3"]
        assert a3["status"] == "running"

    def test_corrupt_checkpoint_ignored(self, client, arena3_dir):
        (arena3_dir / "BULL_TREND.json").write_text("BROKEN")
        resp = client.get("/api/arena")
        a3 = resp.json()["arena3"]
        bull = next(r for r in a3["regimes"] if r["name"] == "BULL_TREND")
        assert bull["status"] == "pending"
        assert bull["gen"] == 0


# ---------------------------------------------------------------------------
# Integration — full response shape
# ---------------------------------------------------------------------------


class TestFullResponse:
    def test_response_shape(self, client):
        resp = client.get("/api/arena")
        data = resp.json()
        assert set(data.keys()) == {"arena1", "arena2", "arena3"}
        assert "status" in data["arena1"]
        assert "completed_runs" in data["arena1"]
        assert "total_runs" in data["arena1"]
        assert "status" in data["arena2"]
        assert "factor_count" in data["arena2"]
        assert "status" in data["arena3"]
        assert "regimes" in data["arena3"]
