use crate::types::*;

// ─── Helper: True Range ───
fn true_range_vec(high: &[f64], low: &[f64], close: &[f64]) -> Vec<f64> {
    let n = high.len();
    let mut tr = vec![0.0; n];
    tr[0] = high[0] - low[0];
    for i in 1..n {
        let hl = high[i] - low[i];
        let hc = (high[i] - close[i - 1]).abs();
        let lc = (low[i] - close[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);
    }
    tr
}

fn rolling_std(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    let mut out = vec![0.0; n];
    if period < 2 { return out; }
    for i in (period - 1)..n {
        let start = i - period + 1;
        let slice = &data[start..=i];
        let mean: f64 = slice.iter().sum::<f64>() / period as f64;
        let var: f64 = slice.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (period as f64 - 1.0);
        out[i] = var.sqrt();
    }
    out
}

// ─── 1. ATR ───
pub fn atr(data: &OhlcvData, period: usize) -> IndicatorResult {
    let tr = true_range_vec(&data.high, &data.low, &data.close);
    let vals = wilder_smooth(&tr, period);
    IndicatorResult { values: vals }
}

// ─── 2. Bollinger Upper ───
pub fn bollinger_upper(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mid = sma(&data.close, period);
    let sd = rolling_std(&data.close, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = mid[i] + 2.0 * sd[i]; }
    IndicatorResult { values: result }
}

// ─── 3. Bollinger Lower ───
pub fn bollinger_lower(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mid = sma(&data.close, period);
    let sd = rolling_std(&data.close, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = mid[i] - 2.0 * sd[i]; }
    IndicatorResult { values: result }
}

// ─── 4. Bollinger Mid ───
pub fn bollinger_mid(data: &OhlcvData, period: usize) -> IndicatorResult {
    let vals = sma(&data.close, period);
    IndicatorResult { values: vals }
}

// ─── 5. Bollinger Width ───
pub fn bollinger_width(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let upper = bollinger_upper(data, period);
    let lower = bollinger_lower(data, period);
    let mid = sma(&data.close, period);
    let mut result = vec![0.0; n];
    for i in 0..n {
        if mid[i].abs() > 1e-15 {
            result[i] = (upper.values[i] - lower.values[i]) / mid[i];
        }
    }
    IndicatorResult { values: result }
}

// ─── 6. Keltner Upper ───
pub fn keltner_upper(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let multiplier = 2.0;
    let mid = ema(&data.close, period);
    let atr_vals = atr(data, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = mid[i] + multiplier * atr_vals.values[i]; }
    IndicatorResult { values: result }
}

// ─── 7. Keltner Lower ───
pub fn keltner_lower(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let multiplier = 2.0;
    let mid = ema(&data.close, period);
    let atr_vals = atr(data, period);
    let mut result = vec![0.0; n];
    for i in 0..n { result[i] = mid[i] - multiplier * atr_vals.values[i]; }
    IndicatorResult { values: result }
}

// ─── 8. Keltner Mid ───
pub fn keltner_mid(data: &OhlcvData, period: usize) -> IndicatorResult {
    let vals = ema(&data.close, period);
    IndicatorResult { values: vals }
}

// ─── 9. Donchian Upper ───
pub fn donchian_upper(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mx = f64::NEG_INFINITY;
        for j in start..=i {
            if data.high[j] > mx { mx = data.high[j]; }
        }
        result[i] = mx;
    }
    IndicatorResult { values: result }
}

// ─── 10. Donchian Lower ───
pub fn donchian_lower(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    for i in 0..n {
        let start = if i >= period { i - period + 1 } else { 0 };
        let mut mn = f64::INFINITY;
        for j in start..=i {
            if data.low[j] < mn { mn = data.low[j]; }
        }
        result[i] = mn;
    }
    IndicatorResult { values: result }
}

// ─── 11. Donchian Width ───
pub fn donchian_width(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let upper = donchian_upper(data, period);
    let lower = donchian_lower(data, period);
    let mut result = vec![0.0; n];
    for i in 0..n {
        if data.close[i].abs() > 1e-15 {
            result[i] = (upper.values[i] - lower.values[i]) / data.close[i];
        }
    }
    IndicatorResult { values: result }
}

// ─── 12. NATR ───
pub fn natr(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let atr_vals = atr(data, period);
    let mut result = vec![0.0; n];
    for i in 0..n {
        if data.close[i].abs() > 1e-15 {
            result[i] = atr_vals.values[i] / data.close[i] * 100.0;
        }
    }
    IndicatorResult { values: result }
}

// ─── 13. True Range ───
pub fn true_range(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let vals = true_range_vec(&data.high, &data.low, &data.close);
    IndicatorResult { values: vals }
}

// ─── 14. Ulcer Index ───
pub fn ulcer_index(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    for i in (period - 1)..n {
        let start = i - period + 1;
        // Find max close in the lookback window
        let mut max_close = f64::NEG_INFINITY;
        for j in start..=i {
            if data.close[j] > max_close { max_close = data.close[j]; }
        }
        let mut sum_sq = 0.0;
        for j in start..=i {
            let dd_pct = if max_close > 1e-15 {
                (data.close[j] - max_close) / max_close * 100.0
            } else { 0.0 };
            sum_sq += dd_pct * dd_pct;
        }
        result[i] = (sum_sq / period as f64).sqrt();
    }
    IndicatorResult { values: result }
}

// ─── 15. Chaikin Volatility ───
pub fn chaikin_volatility(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    let mut hl = vec![0.0; n];
    for i in 0..n { hl[i] = data.high[i] - data.low[i]; }
    let ema_hl = ema(&hl, period);
    let roc_period = period; // typical: ROC of EMA(H-L) over same period
    for i in roc_period..n {
        if ema_hl[i - roc_period].abs() > 1e-15 {
            result[i] = (ema_hl[i] - ema_hl[i - roc_period]) / ema_hl[i - roc_period] * 100.0;
        }
    }
    IndicatorResult { values: result }
}

// ─── 16. Historical Volatility ───
pub fn historical_volatility(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period < 2 { return IndicatorResult { values: result }; }
    let mut log_ret = vec![0.0; n];
    for i in 1..n {
        if data.close[i - 1] > 1e-15 {
            log_ret[i] = (data.close[i] / data.close[i - 1]).ln();
        }
    }
    let std_vals = rolling_std(&log_ret, period);
    for i in 0..n {
        result[i] = std_vals[i] * (252.0_f64).sqrt();
    }
    IndicatorResult { values: result }
}

// ─── 17. Garman-Klass ───
pub fn garman_klass(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    // Use (high+low)/2 as open proxy since OhlcvData has no open field
    for i in (period - 1)..n {
        let start = i - period + 1;
        let mut sum = 0.0;
        for j in start..=i {
            let o = (data.high[j] + data.low[j]) / 2.0; // open proxy
            let h = data.high[j];
            let l = data.low[j];
            let c = data.close[j];
            if h > 1e-15 && l > 1e-15 && c > 1e-15 && o > 1e-15 {
                let hl = (h / l).ln();
                let co = (c / o).ln();
                sum += 0.5 * hl * hl - (2.0 * 2.0_f64.ln() - 1.0) * co * co;
            }
        }
        result[i] = (sum / period as f64).max(0.0).sqrt();
    }
    IndicatorResult { values: result }
}

// ─── 18. Parkinson ───
pub fn parkinson(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    let factor = 1.0 / (4.0 * period as f64 * 2.0_f64.ln());
    for i in (period - 1)..n {
        let start = i - period + 1;
        let mut sum = 0.0;
        for j in start..=i {
            if data.low[j] > 1e-15 {
                let hl = (data.high[j] / data.low[j]).ln();
                sum += hl * hl;
            }
        }
        result[i] = (factor * sum).max(0.0).sqrt();
    }
    IndicatorResult { values: result }
}

// ─── 19. Rogers-Satchell ───
pub fn rogers_satchell(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if period == 0 { return IndicatorResult { values: result }; }
    // Use (high+low)/2 as open proxy
    for i in (period - 1)..n {
        let start = i - period + 1;
        let mut sum = 0.0;
        for j in start..=i {
            let o = (data.high[j] + data.low[j]) / 2.0;
            let h = data.high[j];
            let l = data.low[j];
            let c = data.close[j];
            if h > 1e-15 && l > 1e-15 && c > 1e-15 && o > 1e-15 {
                sum += (h / c).ln() * (h / o).ln() + (l / c).ln() * (l / o).ln();
            }
        }
        let mean = sum / period as f64;
        result[i] = if mean > 0.0 { mean.sqrt() } else { 0.0 };
    }
    IndicatorResult { values: result }
}

// ─── 20. Yang-Zhang ───
pub fn yang_zhang(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut result = vec![0.0; n];
    if n < 2 || period < 2 { return IndicatorResult { values: result }; }
    // Use (high+low)/2 as open proxy
    for i in (period - 1)..n {
        let start = i - period + 1;

        // Overnight volatility: var(ln(open_i / close_{i-1}))
        let mut overnight = Vec::new();
        for j in start..=i {
            if j > 0 && data.close[j - 1] > 1e-15 {
                let o = (data.high[j] + data.low[j]) / 2.0;
                overnight.push((o / data.close[j - 1]).ln());
            }
        }
        let ov_var = if overnight.len() >= 2 {
            let mean: f64 = overnight.iter().sum::<f64>() / overnight.len() as f64;
            overnight.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (overnight.len() as f64 - 1.0)
        } else { 0.0 };

        // Open-to-close volatility: var(ln(close / open))
        let mut oc = Vec::new();
        for j in start..=i {
            let o = (data.high[j] + data.low[j]) / 2.0;
            if o > 1e-15 {
                oc.push((data.close[j] / o).ln());
            }
        }
        let oc_var = if oc.len() >= 2 {
            let mean: f64 = oc.iter().sum::<f64>() / oc.len() as f64;
            oc.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (oc.len() as f64 - 1.0)
        } else { 0.0 };

        // Rogers-Satchell component
        let mut rs_sum = 0.0;
        for j in start..=i {
            let o = (data.high[j] + data.low[j]) / 2.0;
            let h = data.high[j];
            let l = data.low[j];
            let c = data.close[j];
            if h > 1e-15 && l > 1e-15 && c > 1e-15 && o > 1e-15 {
                rs_sum += (h / c).ln() * (h / o).ln() + (l / c).ln() * (l / o).ln();
            }
        }
        let rs_var = rs_sum / period as f64;

        let k = 0.34 / (1.34 + (period as f64 + 1.0) / (period as f64 - 1.0));
        let total = ov_var + k * oc_var + (1.0 - k) * rs_var;
        result[i] = if total > 0.0 { total.sqrt() } else { 0.0 };
    }
    IndicatorResult { values: result }
}

// ─── 21. Standard Deviation ───
pub fn standard_deviation(data: &OhlcvData, period: usize) -> IndicatorResult {
    let vals = rolling_std(&data.close, period);
    IndicatorResult { values: vals }
}

// ─── Dispatch ───
pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "atr" => Some(atr(data, period)),
        "bollinger_upper" => Some(bollinger_upper(data, period)),
        "bollinger_lower" => Some(bollinger_lower(data, period)),
        "bollinger_mid" => Some(bollinger_mid(data, period)),
        "bollinger_width" => Some(bollinger_width(data, period)),
        "keltner_upper" => Some(keltner_upper(data, period)),
        "keltner_lower" => Some(keltner_lower(data, period)),
        "keltner_mid" => Some(keltner_mid(data, period)),
        "donchian_upper" => Some(donchian_upper(data, period)),
        "donchian_lower" => Some(donchian_lower(data, period)),
        "donchian_width" => Some(donchian_width(data, period)),
        "natr" => Some(natr(data, period)),
        "true_range" => Some(true_range(data, period)),
        "ulcer_index" => Some(ulcer_index(data, period)),
        "chaikin_volatility" => Some(chaikin_volatility(data, period)),
        "historical_volatility" => Some(historical_volatility(data, period)),
        "garman_klass" => Some(garman_klass(data, period)),
        "parkinson" => Some(parkinson(data, period)),
        "rogers_satchell" => Some(rogers_satchell(data, period)),
        "yang_zhang" => Some(yang_zhang(data, period)),
        "standard_deviation" => Some(standard_deviation(data, period)),
        _ => None,
    }
}
