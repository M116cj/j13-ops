from zangetsu.core_factory.economic_arena_adapter import evaluate_candidate

def test_unsupported_op_returns_not_evaluated():
    bad_ast = ('op', 'NOT_AN_OP', (('field', 'close'),))
    r = evaluate_candidate(candidate_id='c1', formula_ast=bad_ast,
                           symbol='BTCUSDT', timeframe='1h', axis_id='C',
                           intended_side_mode='LONG')
    assert r.status == 'NOT_EVALUATED'
    assert r.blocker_reason == 'UNSUPPORTED_OPERATOR'

def test_missing_data_returns_not_evaluated():
    ast = ('field', 'close')
    r = evaluate_candidate(candidate_id='c2', formula_ast=ast,
                           symbol='NOSUCH_SYMBOL', timeframe='1h', axis_id='C',
                           intended_side_mode='LONG')
    assert r.status == 'NOT_EVALUATED'
    assert r.blocker_reason == 'AXIS_COMPONENT_UNAVAILABLE'
