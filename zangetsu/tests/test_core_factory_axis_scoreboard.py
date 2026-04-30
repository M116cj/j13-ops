from zangetsu.core_factory.axis_scoreboard import rank_axes, score_axis

def test_score_total_in_range():
    rec = {
        'axis_id': 'H', 'n_candidates': 128, 'target_candidates': 128,
        'unique_formulas': 32, 'target_unique_formulas': 32,
        'realized_long_trade_count': 100, 'realized_short_trade_count': 80,
        'n_evaluated': 100, 'n_passed': 5, 'n_near_survivors': 10,
        'n_rejected': 95, 'n_unknown_reject': 0,
        'avg_net_bps': -1.5, 'feedback_status': 'OK',
    }
    s = score_axis(rec)
    assert 0 <= s['total'] <= 100
    assert s['axis_id'] == 'H'

def test_rank_orders_by_total():
    recs = [
        {'axis_id': 'A', 'n_candidates': 10, 'target_candidates': 100, 'unique_formulas': 0,
         'target_unique_formulas': 32, 'n_evaluated': 0, 'n_passed': 0,
         'n_rejected': 0, 'n_unknown_reject': 0, 'n_near_survivors': 0,
         'realized_long_trade_count': 0, 'realized_short_trade_count': 0,
         'avg_net_bps': -50, 'feedback_status': 'EMPTY_WITH_REASON'},
        {'axis_id': 'B', 'n_candidates': 100, 'target_candidates': 100, 'unique_formulas': 32,
         'target_unique_formulas': 32, 'n_evaluated': 100, 'n_passed': 5,
         'n_rejected': 95, 'n_unknown_reject': 0, 'n_near_survivors': 5,
         'realized_long_trade_count': 50, 'realized_short_trade_count': 50,
         'avg_net_bps': 1.0, 'feedback_status': 'OK'},
    ]
    out = rank_axes(recs)
    assert out[0]['axis_id'] == 'B'
    assert out[0]['rank'] == 1
