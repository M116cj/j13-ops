"""Aggregate reject reasons → feedback weights.

Important rule (per order §8): NOT_EVALUATED candidates MUST NOT contribute to
economic feedback. Only evaluated REJECTED candidates produce feedback.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping


def summarize_reject_reasons(results: Iterable[dict]) -> dict:
    """Build {reject_reason: count} from REJECTED rows only.

    Excludes NOT_EVALUATED, ERROR, and PASSED. Tracks UNKNOWN_REJECT separately.
    """
    counter: Counter[str] = Counter()
    not_evaluated = 0
    error = 0
    passed = 0
    for r in results:
        st = r.get("status")
        if st == "REJECTED":
            reason = r.get("reject_reason") or "UNKNOWN_REJECT"
            counter[reason] += 1
        elif st == "NOT_EVALUATED":
            not_evaluated += 1
        elif st == "ERROR":
            error += 1
        elif st == "PASSED":
            passed += 1
    return {
        "rejected_by_reason": dict(counter),
        "rejected_total": int(sum(counter.values())),
        "unknown_reject_count": int(counter.get("UNKNOWN_REJECT", 0)),
        "not_evaluated_total": int(not_evaluated),
        "error_total": int(error),
        "passed_total": int(passed),
    }


def feedback_weights_from_summary(summary: dict) -> dict:
    """Generate feedback weights ONLY from evaluated rejections.

    If rejected_total == 0, return an empty payload with a reason — never fake.
    """
    rejected = summary.get("rejected_by_reason", {})
    total = summary.get("rejected_total", 0)
    if total == 0:
        return {
            "weights": {},
            "status": "EMPTY_WITH_REASON",
            "reason": "no_evaluated_rejections",
        }
    weights = {k: float(v) / float(total) for k, v in rejected.items()}
    return {
        "weights": weights,
        "status": "OK",
        "reason": None,
    }
