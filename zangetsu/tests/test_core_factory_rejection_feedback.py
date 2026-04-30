from zangetsu.core_factory.rejection_feedback import (
    feedback_weights_from_summary, summarize_reject_reasons,
)

def test_not_evaluated_does_not_contribute_to_feedback():
    rows = [
        {'status': 'NOT_EVALUATED', 'reject_reason': None},
        {'status': 'REJECTED', 'reject_reason': 'too_few_trades'},
        {'status': 'REJECTED', 'reject_reason': 'too_few_trades'},
        {'status': 'REJECTED', 'reject_reason': 'non_positive_net'},
    ]
    s = summarize_reject_reasons(rows)
    assert s['rejected_total'] == 3
    assert s['not_evaluated_total'] == 1
    fw = feedback_weights_from_summary(s)
    assert fw['status'] == 'OK'
    assert abs(sum(fw['weights'].values()) - 1.0) < 1e-9

def test_no_rejections_yields_empty_with_reason():
    rows = [{'status': 'NOT_EVALUATED'}, {'status': 'PASSED'}]
    s = summarize_reject_reasons(rows)
    fw = feedback_weights_from_summary(s)
    assert fw['status'] == 'EMPTY_WITH_REASON'
    assert fw['weights'] == {}
