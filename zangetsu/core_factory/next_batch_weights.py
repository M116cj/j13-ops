"""next_batch_weights generator (0-9AD).

Maps reject reasons in the current batch to recommended generator-weight
adjustments for the next batch. Rules taken verbatim from order section 9.

NEVER fabricates; if there are no evaluated rejections, returns
EMPTY_WITH_REASON.
"""

from __future__ import annotations

from typing import Iterable


REASON_TO_ACTION: dict[str, dict] = {
    'no_trades_generated': {
        'failure_mode': 'NO_TRADES_GENERATED',
        'action': 'increase_trigger_density_or_adjust_regime_condition',
        'grammar_weight_delta': -0.10,
    },
    'non_positive_net': {
        'failure_mode': 'TRAIN_NEG_PNL',
        'action': 'reduce_similar_grammar_family',
        'grammar_weight_delta': -0.20,
    },
    'too_few_trades': {
        'failure_mode': 'SIGNAL_TOO_SPARSE',
        'action': 'increase_denser_signal_variants',
        'grammar_weight_delta': -0.15,
    },
    'UNKNOWN_REJECT': {
        'failure_mode': 'UNKNOWN_REJECT',
        'action': 'flag_taxonomy_gap',
        'grammar_weight_delta': 0.0,
    },
}


def next_batch_weights_from_summary(summary: dict) -> dict:
    """Translate a reject-reason summary into next-batch generator weights.

    summary should match the shape produced by rejection_feedback.summarize_reject_reasons.
    """
    rejected_by_reason = summary.get('rejected_by_reason', {}) or {}
    rejected_total = int(summary.get('rejected_total', 0) or 0)
    if rejected_total == 0:
        return {
            'based_on': 'no_evaluated_rejections',
            'status': 'EMPTY_WITH_REASON',
            'reason': summary.get('blocker_reason') or 'no_evaluated_rejections_yet',
            'by_reason': {},
            'unknown_reject_count': int(summary.get('unknown_reject_count', 0) or 0),
            'recommended_actions': [],
        }
    by_reason = {}
    actions: list[dict] = []
    for reason, count in rejected_by_reason.items():
        spec = REASON_TO_ACTION.get(reason, {
            'failure_mode': 'OTHER',
            'action': 'no_explicit_mapping',
            'grammar_weight_delta': 0.0,
        })
        share = float(count) / float(rejected_total)
        entry = {
            'count': int(count),
            'share': round(share, 6),
            **spec,
        }
        by_reason[reason] = entry
        if abs(spec.get('grammar_weight_delta', 0.0)) > 1e-9 and share >= 0.05:
            actions.append({
                'reason': reason, 'failure_mode': spec['failure_mode'],
                'action': spec['action'],
                'grammar_weight_delta': spec['grammar_weight_delta'],
                'share': round(share, 6),
            })
    actions.sort(key=lambda a: a['share'], reverse=True)
    return {
        'based_on': 'evaluated_rejections',
        'status': 'OK',
        'rejected_total': rejected_total,
        'unknown_reject_count': int(summary.get('unknown_reject_count', 0) or 0),
        'by_reason': by_reason,
        'recommended_actions': actions,
    }


def actions_above_threshold(weights: dict, *, share_threshold: float = 0.10) -> list[dict]:
    """Return recommended_actions whose share >= threshold (default 10%)."""
    return [a for a in weights.get('recommended_actions', [])
            if a.get('share', 0.0) >= share_threshold]
