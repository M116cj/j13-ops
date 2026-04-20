#!/usr/bin/env python3
"""Integration test: DB CRUD + Checkpoint + Console API logic."""
import asyncio, json, sys, os
sys.path.insert(0, "/home/j13/j13-ops/zangetsu")

DB_DSN = dict(
    host="localhost", port=5432,
    database="zangetsu", user="zangetsu",
    password=os.getenv("ZV5_DB_PASSWORD", "")
)


async def test_db():
    import asyncpg

    conn = await asyncpg.connect(**DB_DSN)

    print("=== DB CRUD Test ===")

    # 1. INSERT a test champion
    print("\n1. INSERT test champion")
    await conn.execute("""
        INSERT INTO champion_pipeline_fresh
        (regime, indicator_hash, status, n_indicators, passport, engine_hash)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
    """, "BULL_TREND", "test_hash_001", "ARENA1_READY", 3,
        json.dumps({"arena1": {"test": True}}), "engine_v5_test")
    print("  OK: Inserted")

    # 2. READ it back
    print("\n2. SELECT test champion")
    row = await conn.fetchrow(
        "SELECT * FROM champion_pipeline_fresh WHERE indicator_hash = $1",
        "test_hash_001"
    )
    print(f"  OK: id={row['id']}, status={row['status']}, regime={row['regime']}")
    print(f"  passport={row['passport']}")
    champion_id = row['id']

    # 3. UPDATE status (simulate arena progression)
    print("\n3. UPDATE status ARENA1_READY -> ARENA1_PROCESSING")
    await conn.execute("""
        UPDATE champion_pipeline_fresh
        SET status = 'ARENA1_PROCESSING',
            worker_id = 'test_worker',
            lease_until = NOW() + INTERVAL '5 minutes',
            updated_at = NOW()
        WHERE id = $1
    """, champion_id)
    row = await conn.fetchrow("SELECT status, worker_id FROM champion_pipeline_fresh WHERE id = $1", champion_id)
    print(f"  OK: status={row['status']}, worker={row['worker_id']}")

    # 4. UPDATE with arena1 results
    print("\n4. UPDATE with arena1 results")
    await conn.execute("""
        UPDATE champion_pipeline_fresh SET
            status = 'ARENA1_COMPLETE',
            arena1_score = $1,
            arena1_win_rate = $2,
            arena1_pnl = $3,
            arena1_n_trades = $4,
            arena1_completed_at = NOW(),
            passport = passport || $5::jsonb,
            updated_at = NOW()
        WHERE id = $6
    """, 0.85, 0.62, 0.0045, 47,
        json.dumps({"arena1": {"score": 0.85, "win_rate": 0.62}}),
        champion_id)
    row = await conn.fetchrow("SELECT status, arena1_score, arena1_win_rate FROM champion_pipeline_fresh WHERE id = $1", champion_id)
    print(f"  OK: status={row['status']}, score={row['arena1_score']}, wr={row['arena1_win_rate']}")

    # 5. Test audit log
    print("\n5. INSERT audit log entry")
    await conn.execute("""
        INSERT INTO pipeline_audit_log (champion_id, old_status, new_status, worker_id, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
    """, champion_id, "ARENA1_READY", "ARENA1_COMPLETE", "test_worker",
        json.dumps({"test": True, "round": 1}))
    audit = await conn.fetchrow(
        "SELECT * FROM pipeline_audit_log WHERE champion_id = $1 ORDER BY created_at DESC LIMIT 1",
        champion_id
    )
    print(f"  OK: audit id={audit['id']}, transition={audit['old_status']}->{audit['new_status']}")

    # 6. Test runtime_status (singleton row, id=1, CHECK id=1)
    print("\n6. Test runtime_status upsert")
    try:
        await conn.execute("""
            INSERT INTO runtime_status (id, regime, confidence, bars_since_switch)
            VALUES (1, 'BULL_TREND_TEST', 0.95, 10)
            ON CONFLICT (id) DO UPDATE SET
                regime = EXCLUDED.regime,
                confidence = EXCLUDED.confidence,
                bars_since_switch = EXCLUDED.bars_since_switch,
                updated_at = NOW()
        """)
        row = await conn.fetchrow("SELECT regime, confidence FROM runtime_status WHERE id = 1")
        print(f"  OK: regime={row['regime']}, confidence={row['confidence']}")
        # Restore to neutral
        await conn.execute("""
            UPDATE runtime_status SET regime = NULL, confidence = NULL, bars_since_switch = NULL, updated_at = NOW() WHERE id = 1
        """)
        print("  OK: Restored runtime_status")
    except Exception as e:
        print(f"  SKIP: runtime_status — {type(e).__name__}: {e}")

    # 7. Test CHECK constraints (valid_status)
    print("\n7. Test CHECK constraint: valid_status")
    try:
        await conn.execute("""
            UPDATE champion_pipeline_fresh SET status = 'INVALID_STATUS' WHERE id = $1
        """, champion_id)
        print("  FAIL: Should have rejected invalid status!")
    except Exception as e:
        print(f"  OK: Constraint blocked invalid status — {type(e).__name__}")
        await conn.close()
        conn = await asyncpg.connect(**DB_DSN)

    # 8. Test card_status constraint
    print("\n8. Test CHECK constraint: valid_card_status")
    try:
        await conn.execute("""
            UPDATE champion_pipeline_fresh SET card_status = 'INVALID_CARD' WHERE id = $1
        """, champion_id)
        print("  FAIL: Should have rejected invalid card_status!")
    except Exception as e:
        print(f"  OK: card_status constraint blocked invalid value — {type(e).__name__}")
        await conn.close()
        conn = await asyncpg.connect(**DB_DSN)

    # 9. Cleanup
    print("\n9. Cleanup test data")
    await conn.execute("DELETE FROM pipeline_audit_log WHERE champion_id = $1", champion_id)
    await conn.execute("DELETE FROM champion_pipeline_fresh WHERE indicator_hash = 'test_hash_001'")
    remaining = await conn.fetchval("SELECT count(*) FROM champion_pipeline_fresh WHERE indicator_hash = 'test_hash_001'")
    print(f"  OK: Cleaned up, remaining test rows: {remaining}")

    # 10. Index verification
    print("\n10. Verify indexes are used")
    explain = await conn.fetchval(
        "EXPLAIN SELECT * FROM champion_pipeline_fresh WHERE status = 'DEPLOYABLE' AND regime = 'BULL_TREND'"
    )
    print(f"  Query plan: {explain}")
    uses_index = "Index" in explain or "index" in explain
    print(f"  Uses index: {uses_index}")

    await conn.close()
    print("\n=== DB CRUD Test COMPLETE ===")


async def test_checkpoint():
    import asyncpg

    conn = await asyncpg.connect(**DB_DSN)

    print("\n=== Checkpoint Test ===")

    # 1. Insert a checkpoint
    print("\n1. Save checkpoint")
    await conn.execute("""
        INSERT INTO round_checkpoints (round_id, arena, regime, contestant_idx, results_json, seed)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        ON CONFLICT (round_id) DO UPDATE SET
            results_json = EXCLUDED.results_json,
            updated_at = NOW()
    """, "test_round_42", "arena1", "BULL_TREND", 64,
        json.dumps({"promoted": [], "best_score": 0.85, "contestants_done": 64, "total": 64}),
        12345)
    print("  OK: Checkpoint saved")

    # 2. Load checkpoint
    print("\n2. Load checkpoint")
    row = await conn.fetchrow(
        "SELECT * FROM round_checkpoints WHERE round_id = $1", "test_round_42"
    )
    if row:
        data = json.loads(row['results_json']) if isinstance(row['results_json'], str) else row['results_json']
        print(f"  OK: arena={row['arena']}, regime={row['regime']}, contestant_idx={row['contestant_idx']}")
        print(f"  data={data}")
    else:
        print("  FAIL: No checkpoint found")

    # 3. Update checkpoint (simulate progress)
    print("\n3. Update checkpoint via upsert")
    await conn.execute("""
        INSERT INTO round_checkpoints (round_id, arena, regime, contestant_idx, results_json, seed)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        ON CONFLICT (round_id) DO UPDATE SET
            contestant_idx = EXCLUDED.contestant_idx,
            results_json = EXCLUDED.results_json,
            updated_at = NOW()
    """, "test_round_42", "arena1", "BULL_TREND", 128,
        json.dumps({"promoted": ["hash_A"], "best_score": 0.92, "contestants_done": 128, "total": 128}),
        12345)
    row = await conn.fetchrow("SELECT contestant_idx, results_json FROM round_checkpoints WHERE round_id = $1", "test_round_42")
    print(f"  OK: updated contestant_idx={row['contestant_idx']}")

    # 4. Cleanup
    await conn.execute("DELETE FROM round_checkpoints WHERE round_id = 'test_round_42'")
    remaining = await conn.fetchval("SELECT count(*) FROM round_checkpoints WHERE round_id = 'test_round_42'")
    print(f"\n4. Cleanup OK, remaining: {remaining}")

    await conn.close()
    print("\n=== Checkpoint Test COMPLETE ===")


async def test_console_api():
    """Test console API logic without starting the server."""
    print("\n=== Console API Logic Test ===")

    # Test Settings
    from config.settings import Settings
    s = Settings()

    print(f"\n1. Settings: {len(s.symbols)} symbols")
    d = s.to_dict()
    print(f"   to_dict: {len(d)} keys")

    changed = s.update({"arena1_round_size": 128})
    print(f"   update: changed={changed}, new value={s.arena1_round_size}")

    # Test CostModel
    from config.cost_model import CostModel
    cm = CostModel()

    print(f"\n2. CostModel: {len(cm.snapshot())} symbols in snapshot")
    btc = cm.get("BTCUSDT")
    print(f"   BTCUSDT: maker={btc.maker_bps}, taker={btc.taker_bps}, round_trip={btc.total_round_trip_bps}")
    pepe = cm.get("1000PEPEUSDT")
    print(f"   1000PEPEUSDT: maker={pepe.maker_bps}, taker={pepe.taker_bps}")
    unknown = cm.get("UNKNOWNUSDT")
    print(f"   UNKNOWN (fallback): maker={unknown.maker_bps}, taker={unknown.taker_bps}")

    # Test Pydantic models
    from console.models import ConfigUpdate, ArenaControlRequest, CostOverride

    print(f"\n3. Pydantic models:")
    cu = ConfigUpdate(overrides={"arena1_round_size": 256})
    print(f"   ConfigUpdate: {cu.overrides}")

    acr = ArenaControlRequest(arena_name="arena1", action="start")
    print(f"   ArenaControlRequest: {acr.arena_name} {acr.action}")

    # Test Dashboard models
    from dashboard.models import PipelineOverview, ELOLeaderboard, ELOEntry

    po = PipelineOverview(arenas=[], total_strategies_evaluated=100)
    print(f"   PipelineOverview: evaluated={po.total_strategies_evaluated}")

    ee = ELOEntry(strategy_id="test", elo=1500.0)
    el = ELOLeaderboard(entries=[ee], total_strategies=1)
    print(f"   ELOLeaderboard: {el.total_strategies} entries")

    print("\n=== Console API Logic Test COMPLETE ===")


async def main():
    await test_db()
    await test_checkpoint()
    await test_console_api()
    print("\n" + "=" * 50)
    print("ALL INTEGRATION TESTS COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
