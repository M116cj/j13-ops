"""LONG / SHORT / BOTH / COMBINED aggregate.

Preserves intended_side_mode metadata. Realized long/short counts come from the
actual trade simulator output — never fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def aggregate_long_short(rows: Iterable[dict]) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = defaultdict(lambda: {
        'n_candidates': 0, 'n_passed': 0, 'n_rejected': 0,
        'n_not_evaluated': 0, 'n_error': 0,
        'trade_count_sum': 0, 'long_trade_count_sum': 0, 'short_trade_count_sum': 0,
        'gross_bps_sum': 0.0, 'net_bps_sum': 0.0,
    })
    for r in rows:
        key = (r.get('axis_id', '?'), r.get('intended_side_mode', '?'))
        b = buckets[key]
        b['n_candidates'] += 1
        st = r.get('status', '?')
        if st == 'PASSED':
            b['n_passed'] += 1
        elif st == 'REJECTED':
            b['n_rejected'] += 1
        elif st == 'NOT_EVALUATED':
            b['n_not_evaluated'] += 1
        elif st == 'ERROR':
            b['n_error'] += 1
        b['trade_count_sum'] += int(r.get('trade_count', 0) or 0)
        b['long_trade_count_sum'] += int(r.get('long_trade_count', 0) or 0)
        b['short_trade_count_sum'] += int(r.get('short_trade_count', 0) or 0)
        b['gross_bps_sum'] += float(r.get('gross_bps', 0.0) or 0.0)
        b['net_bps_sum'] += float(r.get('net_bps', 0.0) or 0.0)
    out = []
    for (axis, mode), b in sorted(buckets.items()):
        n = b['n_candidates']
        out.append({
            'axis_id': axis, 'intended_side_mode': mode,
            'n_candidates': n, 'n_passed': b['n_passed'],
            'n_rejected': b['n_rejected'], 'n_not_evaluated': b['n_not_evaluated'],
            'n_error': b['n_error'],
            'realized_long_trade_count': b['long_trade_count_sum'],
            'realized_short_trade_count': b['short_trade_count_sum'],
            'trade_count_sum': b['trade_count_sum'],
            'avg_gross_bps': (b['gross_bps_sum'] / n) if n else 0.0,
            'avg_net_bps': (b['net_bps_sum'] / n) if n else 0.0,
        })
    return out
