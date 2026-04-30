"""Axis scoreboard — apply 0-9AB §10 weights to per-axis tournament results.

Categories (weight):
  candidate_generation_success (15)
  formula_diversity (15)
  long_short_balance (10)
  economic_result_quality (25)
  cost_robustness (15)
  reject_reason_quality (10)
  feedback_usability (10)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def _gen_score(rec: dict) -> float:
    target = rec.get('target_candidates', 128)
    n = rec.get('n_candidates', 0)
    return 15.0 * min(1.0, _safe_div(n, target))


def _diversity_score(rec: dict) -> float:
    target = rec.get('target_unique_formulas', 32)
    n = rec.get('unique_formulas', 0)
    return 15.0 * min(1.0, _safe_div(n, target))


def _ls_balance_score(rec: dict) -> float:
    nl = rec.get('realized_long_trade_count', 0)
    ns = rec.get('realized_short_trade_count', 0)
    if nl + ns == 0:
        return 0.0
    bal = min(nl, ns) / max(nl, ns) if max(nl, ns) > 0 else 0.0
    return 10.0 * float(bal)


def _econ_score(rec: dict) -> float:
    n_eval = rec.get('n_evaluated', 0)
    n_total = rec.get('n_candidates', 0)
    eval_ratio = _safe_div(n_eval, n_total)
    pass_ratio = _safe_div(rec.get('n_passed', 0), n_eval) if n_eval else 0.0
    near_ratio = _safe_div(rec.get('n_near_survivors', 0), n_eval) if n_eval else 0.0
    return 25.0 * (0.5 * eval_ratio + 0.4 * pass_ratio + 0.1 * near_ratio)


def _cost_score(rec: dict) -> float:
    avg_net = float(rec.get('avg_net_bps', 0.0))
    if avg_net >= 0.0:
        return 15.0
    if avg_net >= -5.0:
        return 12.0
    if avg_net >= -15.0:
        return 8.0
    if avg_net >= -30.0:
        return 5.0
    return 2.0


def _reject_quality(rec: dict) -> float:
    n_rejected = rec.get('n_rejected', 0)
    if n_rejected == 0:
        return 5.0
    unknown = rec.get('n_unknown_reject', 0)
    return 10.0 * (1.0 - min(1.0, _safe_div(unknown, n_rejected)))


def _feedback_score(rec: dict) -> float:
    if rec.get('feedback_status') == 'OK':
        return 10.0
    if rec.get('feedback_status') == 'EMPTY_WITH_REASON':
        return 5.0
    return 0.0


def score_axis(rec: dict) -> dict:
    parts = {
        'candidate_generation': round(_gen_score(rec), 2),
        'formula_diversity': round(_diversity_score(rec), 2),
        'long_short_balance': round(_ls_balance_score(rec), 2),
        'economic_result_quality': round(_econ_score(rec), 2),
        'cost_robustness': round(_cost_score(rec), 2),
        'reject_reason_quality': round(_reject_quality(rec), 2),
        'feedback_usability': round(_feedback_score(rec), 2),
    }
    total = round(sum(parts.values()), 2)
    return {'axis_id': rec.get('axis_id'), **parts, 'total': total}


def rank_axes(records: Iterable[dict]) -> list[dict]:
    scored = [score_axis(r) for r in records]
    scored.sort(key=lambda x: x['total'], reverse=True)
    for i, s in enumerate(scored, start=1):
        s['rank'] = i
    return scored
