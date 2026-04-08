"""Regime-conditional backtest on full timeline (V3.2).

Evaluates on the FULL 1m bar timeline with regime masking.
Entry only when regime == target. Exit on signal, stop, hold_max, or regime change (with grace period).
Regime exits use taker fee. Normal exits use maker fee.
"""
from numba import njit
import numpy as np


@njit
def backtest_regime_conditional(
    signal,          # float64[n] — raw signal on ALL bars
    close,           # float64[n] — close prices for ALL bars
    regime_labels,   # int8[n] — regime label per bar
    target_regime,   # int — target regime ID
    entry_thr,       # float
    exit_thr,        # float
    stop_mult,       # float
    pos_frac,        # float
    hold_max,        # int
    grace_period,    # int — bars to wait after regime change before force-exit (default 6)
    maker_bps,       # float — maker fee for normal exits
    taker_bps,       # float — taker fee for regime exits
    funding_rate,    # float
):
    """Backtest with regime-conditional entry and grace-period regime exit.

    Returns: (pnl, pos, exit_type) — pnl, position, and exit type arrays
    """
    n = len(signal)
    pnl = np.zeros(n)
    pos = np.zeros(n, dtype=np.int8)
    exit_type = np.zeros(n, dtype=np.int8)  # 0=none, 1=signal, 2=stop, 3=hold_max, 4=regime
    entry_px = 0.0
    hold = 0
    bars_since_regime_left = 0
    in_grace = False

    for i in range(1, n):
        in_regime = regime_labels[i] == target_regime
        p = pos[i - 1]

        if p != 0:
            # ── IN POSITION ──
            ret = float(p) * (close[i] - close[i - 1]) / close[i - 1] * pos_frac
            pnl[i] = ret

            # Funding every 480 bars (8h)
            if i % 480 == 0:
                pnl[i] -= abs(funding_rate) * pos_frac

            hold += 1

            # Track regime departure
            if not in_regime:
                if not in_grace:
                    in_grace = True
                    bars_since_regime_left = 1
                else:
                    bars_since_regime_left += 1
            else:
                # Regime returned — cancel grace period
                in_grace = False
                bars_since_regime_left = 0

            # Exit conditions
            atr = abs(close[i] - close[i - 1]) * 14.0
            stop_hit = False
            if p > 0 and close[i] < entry_px - stop_mult * atr:
                stop_hit = True
            elif p < 0 and close[i] > entry_px + stop_mult * atr:
                stop_hit = True

            signal_exit = abs(signal[i]) < exit_thr and in_regime
            hold_exit = hold >= hold_max
            regime_exit = in_grace and bars_since_regime_left >= grace_period

            if stop_hit or signal_exit or hold_exit or regime_exit:
                # Determine fee: regime exit → taker, otherwise → maker
                if regime_exit:
                    fee = taker_bps / 10000.0 * pos_frac
                    exit_type[i] = 4
                elif stop_hit:
                    fee = maker_bps / 10000.0 * pos_frac
                    exit_type[i] = 2
                elif hold_exit:
                    fee = maker_bps / 10000.0 * pos_frac
                    exit_type[i] = 3
                else:
                    fee = maker_bps / 10000.0 * pos_frac
                    exit_type[i] = 1
                pnl[i] -= fee
                hold = 0
                in_grace = False
                bars_since_regime_left = 0
                pos[i] = 0
                continue

            pos[i] = p
            continue

        # ── NOT IN POSITION ──
        # Entry only when in target regime AND at 4h boundary
        if not in_regime:
            continue
        if i % 240 != 0:
            continue

        if signal[i] > entry_thr:
            pos[i] = 1
            entry_px = close[i]
            hold = 0
            in_grace = False
            bars_since_regime_left = 0
            pnl[i] -= maker_bps / 10000.0 * pos_frac
        elif signal[i] < -entry_thr:
            pos[i] = -1
            entry_px = close[i]
            hold = 0
            in_grace = False
            bars_since_regime_left = 0
            pnl[i] -= maker_bps / 10000.0 * pos_frac

    return pnl, pos, exit_type


def compute_fold_fitness(pnl, regime_labels, target_regime, min_fold_bars=50, gap_bars=100):
    """Split timeline into folds based on regime episodes. Return trimmed-min of fold PnLs.

    Fold boundaries = points where target_regime has not appeared for >= gap_bars.
    Each fold must have >= min_fold_bars of target_regime presence.
    """
    n = len(pnl)
    in_regime = regime_labels == target_regime

    # Find fold boundaries
    folds = []
    fold_start = None
    bars_without_regime = 0

    for i in range(n):
        if in_regime[i]:
            if fold_start is None:
                fold_start = max(0, i - gap_bars)  # include some context before
            bars_without_regime = 0
        else:
            bars_without_regime += 1
            if fold_start is not None and bars_without_regime >= gap_bars:
                fold_end = i - gap_bars + 1
                regime_bars_in_fold = np.sum(in_regime[fold_start:fold_end])
                if regime_bars_in_fold >= min_fold_bars:
                    folds.append((fold_start, fold_end))
                fold_start = None
                bars_without_regime = 0

    # Handle last fold
    if fold_start is not None:
        regime_bars_in_fold = np.sum(in_regime[fold_start:n])
        if regime_bars_in_fold >= min_fold_bars:
            folds.append((fold_start, n))

    if len(folds) == 0:
        return -999.0, 0, []

    # Compute per-fold PnL
    fold_pnls = []
    for start, end in folds:
        fold_pnl = float(np.sum(pnl[start:end]))
        fold_pnls.append(fold_pnl)

    # Trimmed min: drop worst 1
    arr = np.array(fold_pnls)
    if len(arr) <= 1:
        trimmed = float(arr[0])
    else:
        trimmed = float(np.sort(arr)[1])

    return trimmed, len(folds), fold_pnls


def compute_regime_fitness(pnl, regime_labels, target_regime):
    """Full regime-conditional fitness: sharpe × wr × log1p(tpd) on regime bars only."""
    in_regime = regime_labels == target_regime
    regime_pnl = pnl[in_regime]
    active = regime_pnl[regime_pnl != 0]

    if len(active) < 10:
        return -999.0, 0.0, 0.0, 0

    wr = float(np.mean(active > 0))
    n_days = max(np.sum(in_regime) / 1440.0, 1e-6)
    entries = int(np.sum(np.diff((regime_pnl != 0).astype(np.int8)) == 1))
    tpd = entries / n_days

    mean_a = float(np.mean(active))
    std_a = float(np.std(active))
    if std_a < 1e-15:
        return -999.0, wr, tpd, entries

    active_per_year = len(active) / (np.sum(in_regime) / (1440.0 * 365.0))
    sharpe = mean_a / std_a * np.sqrt(active_per_year)

    if wr < 0.48 or sharpe <= 0:
        return -999.0, wr, tpd, entries

    fitness = float(sharpe * wr * np.log1p(max(tpd, 0.1)))
    return fitness, wr, tpd, entries


def extract_trades_from_backtest(pnl, pos, close, pos_frac, maker_bps, taker_bps,
                                 exit_type_arr=None):
    """Post-hoc trade extractor: parse pnl + position arrays into per-trade records.

    Trade definition:
      0 → ±1 = entry
      ±1 → 0 = exit
      ±1 → ∓1 = exit + reverse entry (2 trades)

    exit_type_arr: int8 array from backtest_regime_conditional.
      0=none, 1=signal, 2=stop, 3=hold_max, 4=regime.
      If None, assumes all exits use maker fee.

    Returns: list of dicts with keys:
      entry_idx, exit_idx, direction, gross_pnl, cost, net_pnl,
      position_size, hold_bars, return_pct
    """
    trades = []
    n = len(pos)
    if n < 2:
        return trades

    entry_idx = None
    direction = 0
    cumulative_pnl = 0.0
    entry_cost = maker_bps / 10000.0 * pos_frac

    for i in range(n):
        prev_pos = pos[i - 1] if i > 0 else 0
        curr_pos = pos[i]

        if prev_pos == 0 and curr_pos != 0:
            # New entry
            entry_idx = i
            direction = int(curr_pos)
            cumulative_pnl = pnl[i]  # includes entry cost deduction

        elif prev_pos != 0 and curr_pos == 0:
            # Exit
            if entry_idx is not None:
                if i != entry_idx:
                    cumulative_pnl += pnl[i]
                hold_bars = i - entry_idx
                entry_price = close[entry_idx]
                # Determine exit fee from exit_type
                is_regime_exit = (exit_type_arr is not None and exit_type_arr[i] == 4)
                exit_fee = (taker_bps if is_regime_exit else maker_bps) / 10000.0 * pos_frac
                cost = entry_cost + exit_fee
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': i,
                    'direction': direction,
                    'net_pnl': float(cumulative_pnl),
                    'gross_pnl': float(cumulative_pnl + cost),
                    'cost': float(cost),
                    'position_size': float(pos_frac),
                    'hold_bars': int(hold_bars),
                    'return_pct': float(cumulative_pnl / (entry_price * pos_frac))
                        if entry_price > 0 and pos_frac > 0 else 0.0,
                })
            entry_idx = None
            direction = 0
            cumulative_pnl = 0.0

        elif prev_pos != 0 and curr_pos != 0 and prev_pos != curr_pos:
            # Reverse: close old + open new (2 trades)
            # pnl[i] contains: old position return + old exit fee + new entry fee
            # We need to split: old trade gets return + old exit fee,
            # new trade gets new entry fee
            if entry_idx is not None:
                # Old trade: accumulate pnl[i] (includes everything at this bar)
                # Then add back the new entry cost that was deducted from pnl[i]
                cumulative_pnl += pnl[i] + entry_cost  # undo new entry cost from old trade
                hold_bars = i - entry_idx
                entry_price = close[entry_idx]
                is_regime_exit = (exit_type_arr is not None and exit_type_arr[i] == 4)
                exit_fee = (taker_bps if is_regime_exit else maker_bps) / 10000.0 * pos_frac
                cost = entry_cost + exit_fee
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': i,
                    'direction': direction,
                    'net_pnl': float(cumulative_pnl),
                    'gross_pnl': float(cumulative_pnl + cost),
                    'cost': float(cost),
                    'position_size': float(pos_frac),
                    'hold_bars': int(hold_bars),
                    'return_pct': float(cumulative_pnl / (entry_price * pos_frac))
                        if entry_price > 0 and pos_frac > 0 else 0.0,
                })
            # New trade starts with only its entry cost
            entry_idx = i
            direction = int(curr_pos)
            cumulative_pnl = -entry_cost  # new trade bears its own entry cost

        elif prev_pos != 0 and curr_pos == prev_pos:
            # Holding — accumulate pnl
            if entry_idx is not None and i != entry_idx:
                cumulative_pnl += pnl[i]

    # Handle unclosed position at end of array
    if entry_idx is not None and direction != 0:
        hold_bars = n - 1 - entry_idx
        entry_price = close[entry_idx]
        cost = entry_cost  # only entry cost, no exit
        trades.append({
            'entry_idx': entry_idx,
            'exit_idx': n - 1,
            'direction': direction,
            'net_pnl': float(cumulative_pnl),
            'gross_pnl': float(cumulative_pnl + cost),
            'cost': float(cost),
            'position_size': float(pos_frac),
            'hold_bars': int(hold_bars),
            'return_pct': float(cumulative_pnl / (entry_price * pos_frac))
                if entry_price > 0 and pos_frac > 0 else 0.0,
        })

    return trades


def compute_trade_level_metrics(trades, years_of_data):
    """Compute trade-level sharpe and related stats.

    Each trade is one observation. Standard quant fund convention for
    HFT-style strategies where active bar count inflates annualization.

    Parameters:
      trades: list of dicts with keys: pnl, cost, funding, position_size
      years_of_data: float, span of data in years

    Returns:
      dict with: trade_level_sharpe, trade_level_sharpe_per_period,
                 expectancy, expectancy_pct, n_trades, trades_per_year,
                 trade_returns, win_rate, avg_win, avg_loss
    """
    empty = {
        'trade_level_sharpe': 0.0,
        'trade_level_sharpe_per_period': 0.0,
        'expectancy': 0.0,
        'expectancy_pct': 0.0,
        'n_trades': 0,
        'trades_per_year': 0.0,
        'trade_returns': np.array([]),
        'win_rate': 0.5,
        'avg_win': 0.0,
        'avg_loss': 0.0,
    }
    if len(trades) < 2:
        if len(trades) == 1:
            empty['n_trades'] = 1
        return empty

    trade_returns = np.array([
        (t['pnl'] - t['cost'] - t.get('funding', 0)) / t['position_size']
        if t['position_size'] > 0 else 0.0
        for t in trades
    ])

    n = len(trade_returns)
    mean_r = float(np.mean(trade_returns))
    std_r = float(np.std(trade_returns, ddof=1))

    if std_r < 1e-12:
        sharpe_per_period = 0.0
    else:
        sharpe_per_period = mean_r / std_r

    trades_per_year = n / years_of_data if years_of_data > 0 else 0.0
    sharpe_annualized = sharpe_per_period * np.sqrt(trades_per_year) if trades_per_year > 0 else 0.0

    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]

    return {
        'trade_level_sharpe': float(sharpe_annualized),
        'trade_level_sharpe_per_period': float(sharpe_per_period),
        'expectancy': float(mean_r),
        'expectancy_pct': float(mean_r * 100),
        'n_trades': int(n),
        'trades_per_year': float(trades_per_year),
        'trade_returns': trade_returns,
        'win_rate': float(len(wins) / n) if n > 0 else 0.5,
        'avg_win': float(np.mean(wins)) if len(wins) > 0 else 0.0,
        'avg_loss': float(abs(np.mean(losses))) if len(losses) > 0 else 0.0,
    }
