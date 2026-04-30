from zangetsu.core_factory.long_short_summary import aggregate_long_short

def test_realized_counts_not_fabricated():
    rows = [
        {'axis_id': 'H', 'intended_side_mode': 'LONG', 'status': 'REJECTED',
         'long_trade_count': 10, 'short_trade_count': 0, 'gross_bps': 1.0,
         'net_bps': -13.5, 'trade_count': 10},
        {'axis_id': 'H', 'intended_side_mode': 'LONG', 'status': 'REJECTED',
         'long_trade_count': 5, 'short_trade_count': 0, 'gross_bps': 2.0,
         'net_bps': -12.5, 'trade_count': 5},
    ]
    out = aggregate_long_short(rows)
    assert len(out) == 1
    assert out[0]['realized_long_trade_count'] == 15
    assert out[0]['realized_short_trade_count'] == 0
