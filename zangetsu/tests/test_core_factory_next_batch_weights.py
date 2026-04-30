from zangetsu.core_factory.next_batch_weights import (
    actions_above_threshold, next_batch_weights_from_summary,
)


def test_empty_with_reason_when_no_rejections():
    s = {'rejected_total': 0, 'rejected_by_reason': {},
         'unknown_reject_count': 0, 'not_evaluated_total': 5,
         'error_total': 0, 'passed_total': 0}
    out = next_batch_weights_from_summary(s)
    assert out['status'] == 'EMPTY_WITH_REASON'
    assert out['by_reason'] == {}
    assert out['recommended_actions'] == []


def test_basic_mapping_share_recorded():
    s = {'rejected_total': 100,
         'rejected_by_reason': {
             'no_trades_generated': 70, 'non_positive_net': 25, 'too_few_trades': 5,
         },
         'unknown_reject_count': 0, 'not_evaluated_total': 0,
         'error_total': 0, 'passed_total': 0}
    out = next_batch_weights_from_summary(s)
    assert out['status'] == 'OK'
    assert out['by_reason']['no_trades_generated']['share'] == 0.70
    assert out['by_reason']['non_positive_net']['failure_mode'] == 'TRAIN_NEG_PNL'
    assert all('grammar_weight_delta' in v for v in out['by_reason'].values())


def test_actions_threshold_filter():
    s = {'rejected_total': 100,
         'rejected_by_reason': {'no_trades_generated': 80, 'too_few_trades': 5,
                                'non_positive_net': 15},
         'unknown_reject_count': 0}
    out = next_batch_weights_from_summary(s)
    big = actions_above_threshold(out, share_threshold=0.20)
    assert any(a['reason'] == 'no_trades_generated' for a in big)
    # too_few_trades has only 5% share → below 20% threshold
    assert all(a['reason'] != 'too_few_trades' for a in big)


def test_unknown_reject_no_weight_change_but_flagged():
    s = {'rejected_total': 100,
         'rejected_by_reason': {'UNKNOWN_REJECT': 100},
         'unknown_reject_count': 100}
    out = next_batch_weights_from_summary(s)
    assert out['by_reason']['UNKNOWN_REJECT']['action'] == 'flag_taxonomy_gap'
    assert out['by_reason']['UNKNOWN_REJECT']['grammar_weight_delta'] == 0.0
