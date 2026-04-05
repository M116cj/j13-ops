"""Gate 3: HFT fitness holdout gate with permanent failure flag (C13)."""

from __future__ import annotations

from dataclasses import dataclass, field

from zangetsu_v3.search.backtest import BacktestResult


@dataclass
class HoldoutGate:
    """One-shot holdout gate. Once failed, permanently returns False (C07)."""
    _failed: bool = field(default=False, init=False, repr=False)

    def gate(
        self,
        holdout_result: BacktestResult,
        *,
        already_tested: bool = False,
    ) -> tuple[bool, str]:
        if already_tested or self._failed:
            return False, "FAILED_HOLDOUT_PERMANENT"

        reasons = []
        if holdout_result.hft_fitness <= 0:
            reasons.append(f"hft_fitness={holdout_result.hft_fitness:.3f}<=0")
        if holdout_result.win_rate < 0.52:
            reasons.append(f"win_rate={holdout_result.win_rate:.3f}<0.52")
        if holdout_result.trades_per_day < 100:
            reasons.append(f"tpd={holdout_result.trades_per_day:.1f}<100")

        if reasons:
            self._failed = True
            return False, "FAILED: " + "; ".join(reasons)
        return True, "PASSED"


__all__ = ["HoldoutGate"]
