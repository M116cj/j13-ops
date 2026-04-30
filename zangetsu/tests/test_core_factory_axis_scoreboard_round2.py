from zangetsu.core_factory.axis_scoreboard import rank_axes


def test_rank_three_axis_scoreboard_round2_winner_lead():
    recs = [
        {'axis_id': 'H', 'n_candidates': 192, 'target_candidates': 192,
         'unique_formulas': 32, 'target_unique_formulas': 32,
         'realized_long_trade_count': 1000, 'realized_short_trade_count': 900,
         'n_evaluated': 192, 'n_passed': 50, 'n_near_survivors': 30,
         'n_rejected': 142, 'n_unknown_reject': 0,
         'avg_net_bps': 1.5, 'feedback_status': 'OK'},
        {'axis_id': 'C', 'n_candidates': 192, 'target_candidates': 192,
         'unique_formulas': 32, 'target_unique_formulas': 32,
         'realized_long_trade_count': 800, 'realized_short_trade_count': 800,
         'n_evaluated': 192, 'n_passed': 5, 'n_near_survivors': 10,
         'n_rejected': 187, 'n_unknown_reject': 0,
         'avg_net_bps': -1.0, 'feedback_status': 'OK'},
        {'axis_id': 'D', 'n_candidates': 192, 'target_candidates': 192,
         'unique_formulas': 32, 'target_unique_formulas': 32,
         'realized_long_trade_count': 100, 'realized_short_trade_count': 100,
         'n_evaluated': 192, 'n_passed': 0, 'n_near_survivors': 50,
         'n_rejected': 192, 'n_unknown_reject': 0,
         'avg_net_bps': -3.0, 'feedback_status': 'OK'},
    ]
    out = rank_axes(recs)
    assert out[0]['rank'] == 1
    # H must outrank C and D given far better economic results
    assert out[0]['axis_id'] == 'H'
    # Ensure totals are floats / no NaN
    for s in out:
        assert isinstance(s['total'], float)
