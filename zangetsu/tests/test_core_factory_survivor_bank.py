from zangetsu.core_factory.survivor_bank import (
    is_near_survivor, is_survivor, split_survivors,
)

def test_passed_is_survivor():
    assert is_survivor({'status': 'PASSED'}) is True
    assert is_near_survivor({'status': 'PASSED'}) is False

def test_not_evaluated_never_survivor():
    assert is_survivor({'status': 'NOT_EVALUATED'}) is False
    assert is_near_survivor({'status': 'NOT_EVALUATED'}) is False

def test_near_survivor_band():
    assert is_near_survivor({'status': 'REJECTED', 'net_bps': -2.0}) is True
    assert is_near_survivor({'status': 'REJECTED', 'net_bps': 0.0}) is True
    assert is_near_survivor({'status': 'REJECTED', 'net_bps': -10.0}) is False
    assert is_near_survivor({'status': 'REJECTED', 'net_bps': 1.0}) is False

def test_split_excludes_not_evaluated():
    rows = [{'status': 'NOT_EVALUATED'}, {'status': 'PASSED'},
            {'status': 'REJECTED', 'net_bps': -3.0}]
    out = split_survivors(rows)
    assert len(out['survivors']) == 1
    assert len(out['near_survivors']) == 1
