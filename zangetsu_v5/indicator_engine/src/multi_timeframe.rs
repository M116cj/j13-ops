use crate::types::*;

/// Multi-timeframe indicators (6 total)
/// Resample data to higher timeframe, compute indicator, forward-fill back.

/// Resample a slice by taking every Nth value
fn resample(data: &[f64], n: usize) -> Vec<f64> {
    if n == 0 { return vec![]; }
    data.iter().step_by(n).cloned().collect()
}

/// Forward-fill resampled results back to original length
fn forward_fill(resampled: &[f64], n: usize, original_len: usize) -> Vec<f64> {
    let mut result = vec![0.0; original_len];
    for (i, &val) in resampled.iter().enumerate() {
        let start = i * n;
        let end = ((i + 1) * n).min(original_len);
        for j in start..end {
            result[j] = val;
        }
    }
    result
}

/// RSI computation (standalone, not depending on other modules)
fn compute_rsi(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if n <= period || period == 0 {
        return vec![0.0; n];
    }
    let mut gains = vec![0.0; n];
    let mut losses = vec![0.0; n];
    for i in 1..n {
        let diff = data[i] - data[i - 1];
        if diff > 0.0 { gains[i] = diff; }
        else { losses[i] = -diff; }
    }
    let mut avg_gain: f64 = gains[1..=period].iter().sum::<f64>() / period as f64;
    let mut avg_loss: f64 = losses[1..=period].iter().sum::<f64>() / period as f64;
    let mut result = vec![0.0; n];
    if avg_loss != 0.0 {
        result[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss);
    } else {
        result[period] = 100.0;
    }
    for i in (period + 1)..n {
        avg_gain = (avg_gain * (period as f64 - 1.0) + gains[i]) / period as f64;
        avg_loss = (avg_loss * (period as f64 - 1.0) + losses[i]) / period as f64;
        if avg_loss != 0.0 {
            result[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss);
        } else {
            result[i] = 100.0;
        }
    }
    result
}

/// EMA computation (standalone)
fn compute_ema(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n < period {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    let seed: f64 = data[..period].iter().sum::<f64>() / period as f64;
    result[period - 1] = seed;
    let alpha = 2.0 / (period as f64 + 1.0);
    for i in period..n {
        result[i] = alpha * data[i] + (1.0 - alpha) * result[i - 1];
    }
    result
}

/// SMA computation (standalone)
fn compute_sma(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n < period {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    let mut sum: f64 = data[..period].iter().sum();
    result[period - 1] = sum / period as f64;
    for i in period..n {
        sum += data[i] - data[i - period];
        result[i] = sum / period as f64;
    }
    result
}

/// MTF RSI — RSI on resampled close (default 240 bars = 4h from 1m)
pub fn mtf_rsi(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1); // resample factor
    let resampled_close = resample(&data.close, n);
    let rsi = compute_rsi(&resampled_close, 14);
    let values = forward_fill(&rsi, n, data.len);
    IndicatorResult { values }
}

/// MTF MACD — MACD on resampled close
pub fn mtf_macd(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1);
    let resampled_close = resample(&data.close, n);
    let ema12 = compute_ema(&resampled_close, 12);
    let ema26 = compute_ema(&resampled_close, 26);
    let macd: Vec<f64> = ema12.iter().zip(ema26.iter()).map(|(a, b)| a - b).collect();
    let values = forward_fill(&macd, n, data.len);
    IndicatorResult { values }
}

/// MTF ADX — ADX on resampled OHLC
pub fn mtf_adx(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1);
    let rs_high = resample(&data.high, n);
    let rs_low = resample(&data.low, n);
    let rs_close = resample(&data.close, n);
    let len = rs_high.len();
    if len < 15 {
        return IndicatorResult { values: vec![0.0; data.len] };
    }
    // True Range, +DM, -DM
    let mut tr = vec![0.0; len];
    let mut plus_dm = vec![0.0; len];
    let mut minus_dm = vec![0.0; len];
    for i in 1..len {
        let h_l = rs_high[i] - rs_low[i];
        let h_pc = (rs_high[i] - rs_close[i - 1]).abs();
        let l_pc = (rs_low[i] - rs_close[i - 1]).abs();
        tr[i] = h_l.max(h_pc).max(l_pc);
        let up = rs_high[i] - rs_high[i - 1];
        let down = rs_low[i - 1] - rs_low[i];
        if up > down && up > 0.0 { plus_dm[i] = up; }
        if down > up && down > 0.0 { minus_dm[i] = down; }
    }
    // Wilder smooth over 14
    let adx_period = 14;
    let smooth_tr = wilder_smooth_vec(&tr, adx_period);
    let smooth_plus = wilder_smooth_vec(&plus_dm, adx_period);
    let smooth_minus = wilder_smooth_vec(&minus_dm, adx_period);
    let mut dx = vec![0.0; len];
    for i in 0..len {
        if smooth_tr[i] != 0.0 {
            let plus_di = 100.0 * smooth_plus[i] / smooth_tr[i];
            let minus_di = 100.0 * smooth_minus[i] / smooth_tr[i];
            let sum = plus_di + minus_di;
            if sum != 0.0 {
                dx[i] = 100.0 * (plus_di - minus_di).abs() / sum;
            }
        }
    }
    let adx = wilder_smooth_vec(&dx, adx_period);
    let values = forward_fill(&adx, n, data.len);
    IndicatorResult { values }
}

fn wilder_smooth_vec(data: &[f64], period: usize) -> Vec<f64> {
    let n = data.len();
    if period == 0 || n < period {
        return vec![0.0; n];
    }
    let mut result = vec![0.0; n];
    let seed: f64 = data[1..=period].iter().sum::<f64>() / period as f64;
    result[period] = seed;
    for i in (period + 1)..n {
        result[i] = (result[i - 1] * (period as f64 - 1.0) + data[i]) / period as f64;
    }
    result
}

/// MTF BB Width — Bollinger Band width on resampled close
pub fn mtf_bb_width(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1);
    let resampled_close = resample(&data.close, n);
    let bb_period = 20;
    let len = resampled_close.len();
    let sma_vals = compute_sma(&resampled_close, bb_period);
    let mut width = vec![0.0; len];
    for i in (bb_period - 1)..len {
        let slice = &resampled_close[(i + 1 - bb_period)..=i];
        let mean = sma_vals[i];
        let var: f64 = slice.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / bb_period as f64;
        let std = var.sqrt();
        if mean != 0.0 {
            width[i] = 4.0 * std / mean; // (upper - lower) / middle
        }
    }
    let values = forward_fill(&width, n, data.len);
    IndicatorResult { values }
}

/// MTF Volume — Volume SMA on resampled volume
pub fn mtf_volume(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1);
    let resampled_vol = resample(&data.volume, n);
    let sma_vals = compute_sma(&resampled_vol, 20);
    let values = forward_fill(&sma_vals, n, data.len);
    IndicatorResult { values }
}

/// MTF ATR — ATR on resampled OHLC
pub fn mtf_atr(period: usize, data: &OhlcvData) -> IndicatorResult {
    let n = period.max(1);
    let rs_high = resample(&data.high, n);
    let rs_low = resample(&data.low, n);
    let rs_close = resample(&data.close, n);
    let len = rs_high.len();
    let atr_period = 14;
    if len < atr_period + 1 {
        return IndicatorResult { values: vec![0.0; data.len] };
    }
    let mut tr = vec![0.0; len];
    for i in 1..len {
        let h_l = rs_high[i] - rs_low[i];
        let h_pc = (rs_high[i] - rs_close[i - 1]).abs();
        let l_pc = (rs_low[i] - rs_close[i - 1]).abs();
        tr[i] = h_l.max(h_pc).max(l_pc);
    }
    let atr = wilder_smooth_vec(&tr, atr_period);
    let values = forward_fill(&atr, n, data.len);
    IndicatorResult { values }
}

pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    match name {
        "mtf_rsi" => Some(mtf_rsi(period, data)),
        "mtf_macd" => Some(mtf_macd(period, data)),
        "mtf_adx" => Some(mtf_adx(period, data)),
        "mtf_bb_width" => Some(mtf_bb_width(period, data)),
        "mtf_volume" => Some(mtf_volume(period, data)),
        "mtf_atr" => Some(mtf_atr(period, data)),
        _ => None,
    }
}
