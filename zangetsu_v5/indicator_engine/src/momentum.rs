use crate::types::*;

/// 1. RSI — Relative Strength Index (Wilder's smoothing)
fn compute_rsi(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period >= n {
        return IndicatorResult { values };
    }
    let mut avg_gain = 0.0;
    let mut avg_loss = 0.0;
    for i in 1..=period {
        let diff = data.close[i] - data.close[i - 1];
        if diff > 0.0 { avg_gain += diff; } else { avg_loss += diff.abs(); }
    }
    avg_gain /= period as f64;
    avg_loss /= period as f64;
    values[period] = if avg_loss < 1e-15 { 100.0 } else { 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) };

    for i in (period + 1)..n {
        let diff = data.close[i] - data.close[i - 1];
        let gain = if diff > 0.0 { diff } else { 0.0 };
        let loss = if diff < 0.0 { diff.abs() } else { 0.0 };
        avg_gain = (avg_gain * (period as f64 - 1.0) + gain) / period as f64;
        avg_loss = (avg_loss * (period as f64 - 1.0) + loss) / period as f64;
        values[i] = if avg_loss < 1e-15 { 100.0 } else { 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) };
    }
    IndicatorResult { values }
}

/// 2. MACD — Moving Average Convergence Divergence (returns MACD line)
fn compute_macd(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let ema12 = ema(&data.close, 12);
    let ema26 = ema(&data.close, 26);
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema12[i] != 0.0 && ema26[i] != 0.0 {
            values[i] = ema12[i] - ema26[i];
        }
    }
    IndicatorResult { values }
}

/// 3. Stochastic K
fn compute_stoch_k(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    for i in (period - 1)..n {
        let start = i + 1 - period;
        let mut hh = f64::MIN;
        let mut ll = f64::MAX;
        for j in start..=i {
            hh = hh.max(data.high[j]);
            ll = ll.min(data.low[j]);
        }
        let range = hh - ll;
        values[i] = if range > 1e-15 { 100.0 * (data.close[i] - ll) / range } else { 50.0 };
    }
    IndicatorResult { values }
}

/// 4. Stochastic D — SMA(3) of Stochastic K
fn compute_stoch_d(data: &OhlcvData, period: usize) -> IndicatorResult {
    let k = compute_stoch_k(data, period);
    IndicatorResult { values: sma(&k.values, 3) }
}

/// 5. CCI — Commodity Channel Index
fn compute_cci(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    // Typical Price
    let mut tp = vec![0.0; n];
    for i in 0..n {
        tp[i] = (data.high[i] + data.low[i] + data.close[i]) / 3.0;
    }
    let tp_sma = sma(&tp, period);
    for i in (period - 1)..n {
        let start = i + 1 - period;
        let mean = tp_sma[i];
        let mut md = 0.0;
        for j in start..=i {
            md += (tp[j] - mean).abs();
        }
        md /= period as f64;
        values[i] = if md > 1e-15 { (tp[i] - mean) / (0.015 * md) } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 6. ROC — Rate of Change
fn compute_roc(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period >= n {
        return IndicatorResult { values };
    }
    for i in period..n {
        let prev = data.close[i - period];
        values[i] = if prev.abs() > 1e-15 { (data.close[i] - prev) / prev * 100.0 } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 7. Williams %R
fn compute_williams_r(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    for i in (period - 1)..n {
        let start = i + 1 - period;
        let mut hh = f64::MIN;
        let mut ll = f64::MAX;
        for j in start..=i {
            hh = hh.max(data.high[j]);
            ll = ll.min(data.low[j]);
        }
        let range = hh - ll;
        values[i] = if range > 1e-15 { -100.0 * (hh - data.close[i]) / range } else { -50.0 };
    }
    IndicatorResult { values }
}

/// 8. MFI — Money Flow Index
fn compute_mfi(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period >= n {
        return IndicatorResult { values };
    }
    let mut tp = vec![0.0; n];
    for i in 0..n {
        tp[i] = (data.high[i] + data.low[i] + data.close[i]) / 3.0;
    }
    for i in period..n {
        let mut pos_flow = 0.0;
        let mut neg_flow = 0.0;
        for j in (i - period + 1)..=i {
            let mf = tp[j] * data.volume[j];
            if tp[j] > tp[j - 1] {
                pos_flow += mf;
            } else if tp[j] < tp[j - 1] {
                neg_flow += mf;
            }
        }
        values[i] = if neg_flow > 1e-15 {
            100.0 - 100.0 / (1.0 + pos_flow / neg_flow)
        } else {
            100.0
        };
    }
    IndicatorResult { values }
}

/// 9. TSI — True Strength Index
fn compute_tsi(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if n < 2 {
        return IndicatorResult { values };
    }
    let mut mom = vec![0.0; n];
    let mut abs_mom = vec![0.0; n];
    for i in 1..n {
        let d = data.close[i] - data.close[i - 1];
        mom[i] = d;
        abs_mom[i] = d.abs();
    }
    // Double smooth: EMA(25) then EMA(13)
    let ds_mom = ema(&ema(&mom, 25), 13);
    let ds_abs = ema(&ema(&abs_mom, 25), 13);
    for i in 0..n {
        values[i] = if ds_abs[i].abs() > 1e-15 { 100.0 * ds_mom[i] / ds_abs[i] } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 10. Ultimate Oscillator — weighted BP/TR over 7,14,28
fn compute_ultimate(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if n < 29 {
        return IndicatorResult { values };
    }
    let mut bp = vec![0.0; n];
    let mut tr = vec![0.0; n];
    for i in 1..n {
        let prev_close = data.close[i - 1];
        let true_low = data.low[i].min(prev_close);
        let true_high = data.high[i].max(prev_close);
        bp[i] = data.close[i] - true_low;
        tr[i] = true_high - true_low;
    }
    for i in 28..n {
        let (mut bp7, mut tr7) = (0.0, 0.0);
        let (mut bp14, mut tr14) = (0.0, 0.0);
        let (mut bp28, mut tr28) = (0.0, 0.0);
        for j in (i - 6)..=i { bp7 += bp[j]; tr7 += tr[j]; }
        for j in (i - 13)..=i { bp14 += bp[j]; tr14 += tr[j]; }
        for j in (i - 27)..=i { bp28 += bp[j]; tr28 += tr[j]; }
        let avg7 = if tr7 > 1e-15 { bp7 / tr7 } else { 0.0 };
        let avg14 = if tr14 > 1e-15 { bp14 / tr14 } else { 0.0 };
        let avg28 = if tr28 > 1e-15 { bp28 / tr28 } else { 0.0 };
        values[i] = 100.0 * (4.0 * avg7 + 2.0 * avg14 + avg28) / 7.0;
    }
    IndicatorResult { values }
}

/// 11. Awesome Oscillator — SMA(5, midpoint) - SMA(34, midpoint)
fn compute_ao(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut mid = vec![0.0; n];
    for i in 0..n {
        mid[i] = (data.high[i] + data.low[i]) / 2.0;
    }
    let sma5 = sma(&mid, 5);
    let sma34 = sma(&mid, 34);
    let mut values = vec![0.0; n];
    for i in 0..n {
        if sma5[i] != 0.0 && sma34[i] != 0.0 {
            values[i] = sma5[i] - sma34[i];
        }
    }
    IndicatorResult { values }
}

/// 12. PPO — Percentage Price Oscillator
fn compute_ppo(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let ema12 = ema(&data.close, 12);
    let ema26 = ema(&data.close, 26);
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema26[i].abs() > 1e-15 {
            values[i] = (ema12[i] - ema26[i]) / ema26[i] * 100.0;
        }
    }
    IndicatorResult { values }
}

/// 13. PMO — Price Momentum Oscillator: double EMA smoothed ROC
fn compute_pmo(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut roc1 = vec![0.0; n];
    for i in 1..n {
        if data.close[i - 1].abs() > 1e-15 {
            roc1[i] = (data.close[i] / data.close[i - 1] - 1.0) * 100.0;
        }
    }
    // PMO = EMA(35) of EMA(20) of ROC*10
    let mut roc10 = vec![0.0; n];
    for i in 0..n { roc10[i] = roc1[i] * 10.0; }
    let smoothed = ema(&ema(&roc10, 35), 20);
    IndicatorResult { values: smoothed }
}

/// 14. CMO — Chande Momentum Oscillator
fn compute_cmo(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period >= n {
        return IndicatorResult { values };
    }
    for i in period..n {
        let mut gains = 0.0;
        let mut losses = 0.0;
        for j in (i - period + 1)..=i {
            let diff = data.close[j] - data.close[j - 1];
            if diff > 0.0 { gains += diff; } else { losses += diff.abs(); }
        }
        let total = gains + losses;
        values[i] = if total > 1e-15 { (gains - losses) / total * 100.0 } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 15. DPO — Detrended Price Oscillator
fn compute_dpo(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    let sma_vals = sma(&data.close, period);
    let shift = period / 2 + 1;
    for i in 0..n {
        if i >= shift && sma_vals[i - shift] != 0.0 {
            values[i] = data.close[i] - sma_vals[i - shift];
        }
    }
    IndicatorResult { values }
}

/// 16. KST — Know Sure Thing: weighted sum of 4 smoothed ROCs
fn compute_kst(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    // ROC periods: 10, 15, 20, 30. SMA periods: 10, 10, 10, 15.
    let roc = |p: usize| -> Vec<f64> {
        let mut r = vec![0.0; n];
        for i in p..n {
            if data.close[i - p].abs() > 1e-15 {
                r[i] = (data.close[i] - data.close[i - p]) / data.close[i - p] * 100.0;
            }
        }
        r
    };
    let r1 = sma(&roc(10), 10);
    let r2 = sma(&roc(15), 10);
    let r3 = sma(&roc(20), 10);
    let r4 = sma(&roc(30), 15);
    let mut values = vec![0.0; n];
    for i in 0..n {
        values[i] = r1[i] * 1.0 + r2[i] * 2.0 + r3[i] * 3.0 + r4[i] * 4.0;
    }
    IndicatorResult { values }
}

/// 17. RVI — Relative Vigor Index
fn compute_rvi(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || n < 4 || period > n {
        return IndicatorResult { values };
    }
    // Smoothed numerator and denominator using symmetric weights [1,2,2,1]/6
    let mut num = vec![0.0; n];
    let mut den = vec![0.0; n];
    for i in 3..n {
        let co = |k: usize| data.close[k] - data.close[k].min(data.high[k]).max(data.low[k]);
        // Actually: (close-open) approximated as close - (high+low)/2 when open unavailable
        // Standard: use (close - open). Since we don't have open, approximate.
        let n0 = data.close[i] - (data.high[i] + data.low[i]) / 2.0;
        let n1 = data.close[i-1] - (data.high[i-1] + data.low[i-1]) / 2.0;
        let n2 = data.close[i-2] - (data.high[i-2] + data.low[i-2]) / 2.0;
        let n3 = data.close[i-3] - (data.high[i-3] + data.low[i-3]) / 2.0;
        num[i] = (n0 + 2.0 * n1 + 2.0 * n2 + n3) / 6.0;

        let d0 = data.high[i] - data.low[i];
        let d1 = data.high[i-1] - data.low[i-1];
        let d2 = data.high[i-2] - data.low[i-2];
        let d3 = data.high[i-3] - data.low[i-3];
        den[i] = (d0 + 2.0 * d1 + 2.0 * d2 + d3) / 6.0;
    }
    let num_sum = sma(&num, period);
    let den_sum = sma(&den, period);
    for i in 0..n {
        values[i] = if den_sum[i].abs() > 1e-15 { num_sum[i] / den_sum[i] } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 18. StochRSI — Stochastic applied to RSI
fn compute_stoch_rsi(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let rsi = compute_rsi(data, period);
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    for i in (period * 2)..n {
        let start = i + 1 - period;
        let mut max_rsi = f64::MIN;
        let mut min_rsi = f64::MAX;
        for j in start..=i {
            max_rsi = max_rsi.max(rsi.values[j]);
            min_rsi = min_rsi.min(rsi.values[j]);
        }
        let range = max_rsi - min_rsi;
        values[i] = if range > 1e-15 { (rsi.values[i] - min_rsi) / range * 100.0 } else { 50.0 };
    }
    IndicatorResult { values }
}

/// 19. Elder Ray Bull Power — high - EMA(close, period)
fn compute_elder_bull(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let ema_vals = ema(&data.close, period);
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema_vals[i] != 0.0 {
            values[i] = data.high[i] - ema_vals[i];
        }
    }
    IndicatorResult { values }
}

/// 20. Elder Ray Bear Power — low - EMA(close, period)
fn compute_elder_bear(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let ema_vals = ema(&data.close, period);
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema_vals[i] != 0.0 {
            values[i] = data.low[i] - ema_vals[i];
        }
    }
    IndicatorResult { values }
}

/// 21. Mass Index — sum of EMA(range)/EMA(EMA(range)) over 25 bars
fn compute_mass_index(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    let mut range = vec![0.0; n];
    for i in 0..n {
        range[i] = data.high[i] - data.low[i];
    }
    let ema_range = ema(&range, 9);
    let ema_ema = ema(&ema_range, 9);
    let mut ratio = vec![0.0; n];
    for i in 0..n {
        ratio[i] = if ema_ema[i].abs() > 1e-15 { ema_range[i] / ema_ema[i] } else { 1.0 };
    }
    // Sum over 25 bars
    for i in 24..n {
        let mut sum = 0.0;
        for j in (i - 24)..=i {
            sum += ratio[j];
        }
        values[i] = sum;
    }
    IndicatorResult { values }
}

/// 22. Chande Forecast Oscillator — 100 * (close - linreg) / close
fn compute_chande_forecast(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period < 2 || period > n {
        return IndicatorResult { values };
    }
    for i in (period - 1)..n {
        let start = i + 1 - period;
        // Linear regression over [start..=i], forecast value at i
        let mut sx = 0.0;
        let mut sy = 0.0;
        let mut sxx = 0.0;
        let mut sxy = 0.0;
        let pf = period as f64;
        for j in 0..period {
            let x = j as f64;
            let y = data.close[start + j];
            sx += x;
            sy += y;
            sxx += x * x;
            sxy += x * y;
        }
        let denom = pf * sxx - sx * sx;
        if denom.abs() > 1e-15 {
            let slope = (pf * sxy - sx * sy) / denom;
            let intercept = (sy - slope * sx) / pf;
            let forecast = intercept + slope * (period as f64 - 1.0);
            if data.close[i].abs() > 1e-15 {
                values[i] = 100.0 * (data.close[i] - forecast) / data.close[i];
            }
        }
    }
    IndicatorResult { values }
}

/// Dispatch function for momentum indicators
pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    let result = match name.to_uppercase().as_str() {
        "RSI" => compute_rsi(data, period),
        "MACD" => compute_macd(data, period),
        "STOCH_K" | "STOCHASTIC_K" => compute_stoch_k(data, period),
        "STOCH_D" | "STOCHASTIC_D" => compute_stoch_d(data, period),
        "CCI" => compute_cci(data, period),
        "ROC" => compute_roc(data, period),
        "WILLIAMS_R" | "WILLR" => compute_williams_r(data, period),
        "MFI" => compute_mfi(data, period),
        "TSI" => compute_tsi(data, period),
        "ULTIMATE" | "UO" => compute_ultimate(data, period),
        "AO" | "AWESOME" => compute_ao(data, period),
        "PPO" => compute_ppo(data, period),
        "PMO" => compute_pmo(data, period),
        "CMO" => compute_cmo(data, period),
        "DPO" => compute_dpo(data, period),
        "KST" => compute_kst(data, period),
        "RVI" => compute_rvi(data, period),
        "STOCH_RSI" | "STOCHRSI" => compute_stoch_rsi(data, period),
        "ELDER_BULL" => compute_elder_bull(data, period),
        "ELDER_BEAR" => compute_elder_bear(data, period),
        "MASS_INDEX" => compute_mass_index(data, period),
        "CHANDE_FORECAST" | "CFO" => compute_chande_forecast(data, period),
        _ => return None,
    };
    Some(result)
}
