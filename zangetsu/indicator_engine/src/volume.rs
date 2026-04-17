use crate::types::*;

// ============================================================
// Volume Indicators — 18 base + 14 micro = 32 total
// ============================================================

/// 1. On Balance Volume
fn obv(data: &OhlcvData) -> IndicatorResult {
    let mut values = Vec::with_capacity(data.len);
    if data.len == 0 {
        return IndicatorResult { values };
    }
    values.push(0.0);
    for i in 1..data.len {
        let prev = *values.last().unwrap();
        if data.close[i] > data.close[i - 1] {
            values.push(prev + data.volume[i]);
        } else if data.close[i] < data.close[i - 1] {
            values.push(prev - data.volume[i]);
        } else {
            values.push(prev);
        }
    }
    IndicatorResult { values }
}

/// 2. VWAP (rolling — no daily reset in this context)
fn vwap(data: &OhlcvData) -> IndicatorResult {
    let mut cum_tp_vol = 0.0;
    let mut cum_vol = 0.0;
    let values: Vec<f64> = (0..data.len)
        .map(|i| {
            let tp = (data.high[i] + data.low[i] + data.close[i]) / 3.0;
            cum_tp_vol += tp * data.volume[i];
            cum_vol += data.volume[i];
            if cum_vol > 0.0 { cum_tp_vol / cum_vol } else { 0.0 }
        })
        .collect();
    IndicatorResult { values }
}

/// 3. Money Flow Index
fn mfi(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < period + 1 {
        return IndicatorResult { values };
    }
    let tp: Vec<f64> = (0..data.len)
        .map(|i| (data.high[i] + data.low[i] + data.close[i]) / 3.0)
        .collect();
    let mf: Vec<f64> = (0..data.len).map(|i| tp[i] * data.volume[i]).collect();

    for i in period..data.len {
        let mut pos = 0.0;
        let mut neg = 0.0;
        for j in (i - period + 1)..=i {
            if tp[j] > tp[j - 1] {
                pos += mf[j];
            } else if tp[j] < tp[j - 1] {
                neg += mf[j];
            }
        }
        values[i] = if neg > 0.0 {
            100.0 - 100.0 / (1.0 + pos / neg)
        } else {
            100.0
        };
    }
    IndicatorResult { values }
}

/// Close Location Value helper
#[inline]
fn clv(high: f64, low: f64, close: f64) -> f64 {
    let hl = high - low;
    if hl > 0.0 {
        ((close - low) - (high - close)) / hl
    } else {
        0.0
    }
}

/// 4. Accumulation/Distribution
fn ad(data: &OhlcvData) -> IndicatorResult {
    let mut values = Vec::with_capacity(data.len);
    let mut cum = 0.0;
    for i in 0..data.len {
        cum += clv(data.high[i], data.low[i], data.close[i]) * data.volume[i];
        values.push(cum);
    }
    IndicatorResult { values }
}

/// 5. Chaikin Money Flow
fn cmf(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < period {
        return IndicatorResult { values };
    }
    for i in (period - 1)..data.len {
        let mut sum_clv_vol = 0.0;
        let mut sum_vol = 0.0;
        for j in (i + 1 - period)..=i {
            sum_clv_vol += clv(data.high[j], data.low[j], data.close[j]) * data.volume[j];
            sum_vol += data.volume[j];
        }
        values[i] = if sum_vol > 0.0 { sum_clv_vol / sum_vol } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 6. Ease of Movement
fn eom(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut raw = vec![0.0; data.len];
    for i in 1..data.len {
        let mid_move = (data.high[i] + data.low[i]) / 2.0 - (data.high[i - 1] + data.low[i - 1]) / 2.0;
        let range = data.high[i] - data.low[i];
        let box_ratio = if range > 0.0 { data.volume[i] / range } else { 0.0 };
        raw[i] = if box_ratio > 0.0 { mid_move / box_ratio } else { 0.0 };
    }
    IndicatorResult { values: sma_vec(&raw, period) }
}

/// 7. Force Index (EMA smoothed)
fn force_index(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut raw = vec![0.0; data.len];
    for i in 1..data.len {
        raw[i] = (data.close[i] - data.close[i - 1]) * data.volume[i];
    }
    IndicatorResult { values: ema_vec(&raw, period) }
}

/// 8. Price Volume Trend
fn pvt(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in 1..data.len {
        let roc = if data.close[i - 1] != 0.0 {
            (data.close[i] - data.close[i - 1]) / data.close[i - 1]
        } else {
            0.0
        };
        values[i] = values[i - 1] + roc * data.volume[i];
    }
    IndicatorResult { values }
}

/// 9. Negative Volume Index
fn nvi(data: &OhlcvData) -> IndicatorResult {
    let mut values = Vec::with_capacity(data.len);
    if data.len == 0 {
        return IndicatorResult { values };
    }
    values.push(1000.0);
    for i in 1..data.len {
        let prev = values[i - 1];
        if data.volume[i] < data.volume[i - 1] && data.close[i - 1] != 0.0 {
            values.push(prev + prev * (data.close[i] - data.close[i - 1]) / data.close[i - 1]);
        } else {
            values.push(prev);
        }
    }
    IndicatorResult { values }
}

/// 10. Positive Volume Index
fn pvi(data: &OhlcvData) -> IndicatorResult {
    let mut values = Vec::with_capacity(data.len);
    if data.len == 0 {
        return IndicatorResult { values };
    }
    values.push(1000.0);
    for i in 1..data.len {
        let prev = values[i - 1];
        if data.volume[i] > data.volume[i - 1] && data.close[i - 1] != 0.0 {
            values.push(prev + prev * (data.close[i] - data.close[i - 1]) / data.close[i - 1]);
        } else {
            values.push(prev);
        }
    }
    IndicatorResult { values }
}

/// 11. Volume Price Trend (same as PVT — canonical alias)
fn vpt(data: &OhlcvData) -> IndicatorResult {
    pvt(data)
}

/// 12. Klinger Volume Oscillator
fn klinger(data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < 2 {
        return IndicatorResult { values };
    }
    // Volume Force: direction * volume * |2*(dm/cm) - 1|
    let mut vf = vec![0.0; data.len];
    let mut cum_dm = 0.0;
    for i in 1..data.len {
        let hlc = data.high[i] + data.low[i] + data.close[i];
        let prev_hlc = data.high[i - 1] + data.low[i - 1] + data.close[i - 1];
        let dm = data.high[i] - data.low[i];
        let trend: f64 = if hlc >= prev_hlc { 1.0 } else { -1.0 };
        // Simplified CM: accumulate dm when trend same, reset otherwise
        let prev_trend: f64 = if i >= 2 {
            let h2 = data.high[i-1] + data.low[i-1] + data.close[i-1];
            let h3 = data.high[i-2] + data.low[i-2] + data.close[i-2];
            if h2 >= h3 { 1.0 } else { -1.0 }
        } else {
            trend
        };
        if trend == prev_trend {
            cum_dm += dm;
        } else {
            cum_dm = dm;
        }
        let cm = cum_dm;
        let ratio = if cm != 0.0 { (2.0 * dm / cm - 1.0).abs() } else { 0.0 };
        vf[i] = trend * data.volume[i] * ratio;
    }
    let ema34 = ema_vec(&vf, 34);
    let ema55 = ema_vec(&vf, 55);
    for i in 0..data.len {
        values[i] = ema34[i] - ema55[i];
    }
    IndicatorResult { values }
}

/// 13. Volume ROC
fn volume_roc(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    for i in period..data.len {
        if data.volume[i - period] != 0.0 {
            values[i] = (data.volume[i] - data.volume[i - period]) / data.volume[i - period] * 100.0;
        }
    }
    IndicatorResult { values }
}

/// 14. Volume SMA
fn volume_sma(period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: sma_vec(&data.volume, period) }
}

/// 15. Volume EMA
fn volume_ema(period: usize, data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: ema_vec(&data.volume, period) }
}

/// 16. Taker Buy Ratio (stub — needs live orderbook data)
fn taker_buy_ratio(data: &OhlcvData) -> IndicatorResult {
    IndicatorResult { values: vec![0.5; data.len] }
}

/// 17. Relative Volume
fn relative_volume(period: usize, data: &OhlcvData) -> IndicatorResult {
    let vol_sma = sma_vec(&data.volume, period);
    let values: Vec<f64> = (0..data.len)
        .map(|i| {
            if vol_sma[i] > 0.0 { data.volume[i] / vol_sma[i] } else { 0.0 }
        })
        .collect();
    IndicatorResult { values }
}

/// 18. Volume Profile POC (simplified: price level with most volume)
fn volume_profile_poc(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    let buckets = 50usize;
    for i in period.saturating_sub(1)..data.len {
        let start = if i >= period { i + 1 - period } else { 0 };
        let mut lo = f64::MAX;
        let mut hi = f64::MIN;
        for j in start..=i {
            if data.low[j] < lo { lo = data.low[j]; }
            if data.high[j] > hi { hi = data.high[j]; }
        }
        let range = hi - lo;
        if range <= 0.0 {
            values[i] = data.close[i];
            continue;
        }
        let step = range / buckets as f64;
        let mut vol_at = vec![0.0f64; buckets];
        for j in start..=i {
            let idx = ((data.close[j] - lo) / step).min((buckets - 1) as f64) as usize;
            vol_at[idx] += data.volume[j];
        }
        let max_idx = vol_at.iter().enumerate().max_by(|a, b| a.1.partial_cmp(b.1).unwrap()).map(|(i, _)| i).unwrap_or(0);
        values[i] = lo + (max_idx as f64 + 0.5) * step;
    }
    IndicatorResult { values }
}

// ============================================================
// Volume Micro Indicators (19-32) — most need tick data
// ============================================================

/// 31. Amihud Illiquidity: avg(|return| / volume)
fn amihud_illiq(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < 2 {
        return IndicatorResult { values };
    }
    for i in period.max(1)..data.len {
        let start = if i >= period { i + 1 - period } else { 1 };
        let mut sum = 0.0;
        let mut count = 0u32;
        for j in start..=i {
            if data.close[j - 1] != 0.0 && data.volume[j] > 0.0 {
                let ret = (data.close[j] - data.close[j - 1]) / data.close[j - 1];
                sum += ret.abs() / data.volume[j];
                count += 1;
            }
        }
        values[i] = if count > 0 { sum / count as f64 } else { 0.0 };
    }
    IndicatorResult { values }
}

/// 32. Roll Spread: 2 * sqrt(-cov(ret_t, ret_{t-1}))
fn roll_spread(period: usize, data: &OhlcvData) -> IndicatorResult {
    let mut values = vec![0.0; data.len];
    if data.len < 3 {
        return IndicatorResult { values };
    }
    let mut rets = vec![0.0; data.len];
    for i in 1..data.len {
        if data.close[i - 1] != 0.0 {
            rets[i] = (data.close[i] - data.close[i - 1]) / data.close[i - 1];
        }
    }
    for i in period.max(2)..data.len {
        let start = if i >= period { i + 1 - period } else { 2 };
        let n = (i - start + 1) as f64;
        if n < 2.0 { continue; }
        let mut sum_x = 0.0;
        let mut sum_y = 0.0;
        for j in start..=i {
            sum_x += rets[j];
            sum_y += rets[j - 1];
        }
        let mean_x = sum_x / n;
        let mean_y = sum_y / n;
        let mut cov = 0.0;
        for j in start..=i {
            cov += (rets[j] - mean_x) * (rets[j - 1] - mean_y);
        }
        cov /= n;
        values[i] = if cov < 0.0 { 2.0 * (-cov).sqrt() } else { 0.0 };
    }
    IndicatorResult { values }
}

/// Stub for tick-level micro indicators
fn stub_zeros(data: &OhlcvData) -> IndicatorResult {
    // Requires tick-level data — returns zeros
    IndicatorResult { values: vec![0.0; data.len] }
}

// ============================================================
// Local helpers (wrap crate helpers for Vec slices)
// ============================================================

fn sma_vec(src: &[f64], period: usize) -> Vec<f64> {
    let mut out = vec![0.0; src.len()];
    if period == 0 || src.len() < period {
        return out;
    }
    let mut sum: f64 = src[..period].iter().sum();
    out[period - 1] = sum / period as f64;
    for i in period..src.len() {
        sum += src[i] - src[i - period];
        out[i] = sum / period as f64;
    }
    out
}

fn ema_vec(src: &[f64], period: usize) -> Vec<f64> {
    let mut out = vec![0.0; src.len()];
    if period == 0 || src.len() < period {
        return out;
    }
    let k = 2.0 / (period as f64 + 1.0);
    let seed: f64 = src[..period].iter().sum::<f64>() / period as f64;
    out[period - 1] = seed;
    for i in period..src.len() {
        out[i] = src[i] * k + out[i - 1] * (1.0 - k);
    }
    out
}

// ============================================================
// Dispatch
// ============================================================

pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        // Base (18)
        "obv" => Some(obv(data)),
        "vwap" => Some(vwap(data)),
        "mfi" => Some(mfi(period, data)),
        "ad" => Some(ad(data)),
        "cmf" => Some(cmf(period, data)),
        "eom" => Some(eom(period, data)),
        "force_index" => Some(force_index(period, data)),
        "pvt" => Some(pvt(data)),
        "nvi" => Some(nvi(data)),
        "pvi" => Some(pvi(data)),
        "vpt" => Some(vpt(data)),
        "klinger" => Some(klinger(data)),
        "volume_roc" => Some(volume_roc(period, data)),
        "volume_sma" => Some(volume_sma(period, data)),
        "volume_ema" => Some(volume_ema(period, data)),
        "taker_buy_ratio" => Some(taker_buy_ratio(data)),
        "relative_volume" => Some(relative_volume(period, data)),
        "volume_profile_poc" => Some(volume_profile_poc(period, data)),
        // Micro — real implementations (2)
        "amihud_illiq" => Some(amihud_illiq(period, data)),
        "roll_spread" => Some(roll_spread(period, data)),
        // Micro — stubs requiring tick data (12)
        "tick_volume" => Some(stub_zeros(data)),
        "trade_intensity" => Some(stub_zeros(data)),
        "buy_sell_ratio" => Some(stub_zeros(data)),
        "large_trade_pct" => Some(stub_zeros(data)),
        "volume_imbalance" => Some(stub_zeros(data)),
        "micro_price" => Some(stub_zeros(data)),
        "trade_flow" => Some(stub_zeros(data)),
        "volume_clock" => Some(stub_zeros(data)),
        "bar_speed" => Some(stub_zeros(data)),
        "tick_speed" => Some(stub_zeros(data)),
        "aggressor_ratio" => Some(stub_zeros(data)),
        "kyle_lambda" => Some(stub_zeros(data)),
        _ => None,
    }
}
