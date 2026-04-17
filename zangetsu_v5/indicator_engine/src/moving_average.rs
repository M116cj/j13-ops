use crate::types::*;

/// 1. SMA — Simple Moving Average
fn compute_sma(data: &OhlcvData, period: usize) -> IndicatorResult {
    IndicatorResult { values: sma(&data.close, period) }
}

/// 2. EMA — Exponential Moving Average
fn compute_ema(data: &OhlcvData, period: usize) -> IndicatorResult {
    IndicatorResult { values: ema(&data.close, period) }
}

/// 3. WMA — Weighted Moving Average
fn compute_wma(data: &OhlcvData, period: usize) -> IndicatorResult {
    IndicatorResult { values: wma(&data.close, period) }
}

/// 4. DEMA — Double EMA: 2*EMA - EMA(EMA)
fn compute_dema(data: &OhlcvData, period: usize) -> IndicatorResult {
    let ema1 = ema(&data.close, period);
    let ema2 = ema(&ema1, period);
    let n = data.len;
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema1[i] != 0.0 && ema2[i] != 0.0 {
            values[i] = 2.0 * ema1[i] - ema2[i];
        }
    }
    IndicatorResult { values }
}

/// 5. TEMA — Triple EMA: 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))
fn compute_tema(data: &OhlcvData, period: usize) -> IndicatorResult {
    let ema1 = ema(&data.close, period);
    let ema2 = ema(&ema1, period);
    let ema3 = ema(&ema2, period);
    let n = data.len;
    let mut values = vec![0.0; n];
    for i in 0..n {
        if ema1[i] != 0.0 && ema2[i] != 0.0 && ema3[i] != 0.0 {
            values[i] = 3.0 * ema1[i] - 3.0 * ema2[i] + ema3[i];
        }
    }
    IndicatorResult { values }
}

/// 6. KAMA — Kaufman Adaptive Moving Average
fn compute_kama(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period >= n || period == 0 {
        return IndicatorResult { values };
    }
    let fast_sc = 2.0 / (2.0 + 1.0);   // fast period = 2
    let slow_sc = 2.0 / (30.0 + 1.0);  // slow period = 30

    values[period - 1] = data.close[period - 1];
    for i in period..n {
        let direction = (data.close[i] - data.close[i - period]).abs();
        let mut volatility = 0.0;
        for j in (i - period + 1)..=i {
            volatility += (data.close[j] - data.close[j - 1]).abs();
        }
        let er = if volatility > 1e-15 { direction / volatility } else { 0.0 };
        let sc = (er * (fast_sc - slow_sc) + slow_sc).powi(2);
        values[i] = values[i - 1] + sc * (data.close[i] - values[i - 1]);
    }
    IndicatorResult { values }
}

/// 7. T3 — Tillson T3: triple-smoothed EMA with volume factor 0.7
fn compute_t3(data: &OhlcvData, period: usize) -> IndicatorResult {
    let vf = 0.7;
    let c1 = -vf * vf * vf;
    let c2 = 3.0 * vf * vf + 3.0 * vf * vf * vf;
    let c3 = -6.0 * vf * vf - 3.0 * vf - 3.0 * vf * vf * vf;
    let c4 = 1.0 + 3.0 * vf + vf * vf * vf + 3.0 * vf * vf;

    let e1 = ema(&data.close, period);
    let e2 = ema(&e1, period);
    let e3 = ema(&e2, period);
    let e4 = ema(&e3, period);
    let e5 = ema(&e4, period);
    let e6 = ema(&e5, period);

    let n = data.len;
    let mut values = vec![0.0; n];
    for i in 0..n {
        if e6[i] != 0.0 {
            values[i] = c1 * e6[i] + c2 * e5[i] + c3 * e4[i] + c4 * e3[i];
        }
    }
    IndicatorResult { values }
}

/// 8. VIDYA — Variable Index Dynamic Average (CMO-based)
fn compute_vidya(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period >= n || period == 0 {
        return IndicatorResult { values };
    }
    let alpha = 2.0 / (period as f64 + 1.0);

    values[period - 1] = data.close[period - 1];
    for i in period..n {
        // CMO over period
        let mut gains = 0.0;
        let mut losses = 0.0;
        for j in (i - period + 1)..=i {
            let diff = data.close[j] - data.close[j - 1];
            if diff > 0.0 { gains += diff; } else { losses += diff.abs(); }
        }
        let cmo_abs = if (gains + losses) > 1e-15 {
            ((gains - losses) / (gains + losses)).abs()
        } else {
            0.0
        };
        values[i] = alpha * cmo_abs * data.close[i] + (1.0 - alpha * cmo_abs) * values[i - 1];
    }
    IndicatorResult { values }
}

/// 9. FRAMA — Fractal Adaptive Moving Average
fn compute_frama(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    let half = period / 2;
    if period < 2 || half == 0 || period >= n {
        return IndicatorResult { values };
    }

    values[period - 1] = data.close[period - 1];
    for i in period..n {
        let start = i - period + 1;
        let mid = start + half;

        // N1 = (max-min) of first half
        let (mut h1, mut l1) = (f64::MIN, f64::MAX);
        for j in start..mid {
            h1 = h1.max(data.high[j]);
            l1 = l1.min(data.low[j]);
        }
        let n1 = (h1 - l1) / half as f64;

        // N2 = (max-min) of second half
        let (mut h2, mut l2) = (f64::MIN, f64::MAX);
        for j in mid..=i {
            h2 = h2.max(data.high[j]);
            l2 = l2.min(data.low[j]);
        }
        let n2 = (h2 - l2) / half as f64;

        // N3 = (max-min) of full period
        let (mut h3, mut l3) = (f64::MIN, f64::MAX);
        for j in start..=i {
            h3 = h3.max(data.high[j]);
            l3 = l3.min(data.low[j]);
        }
        let n3 = (h3 - l3) / period as f64;

        let dim = if n1 + n2 > 1e-15 && n3 > 1e-15 {
            ((n1 + n2).ln() - n3.ln()) / (2.0_f64.ln())
        } else {
            1.0
        };
        let alpha = (-4.6 * (dim - 1.0)).exp().clamp(0.01, 1.0);
        values[i] = alpha * data.close[i] + (1.0 - alpha) * values[i - 1];
    }
    IndicatorResult { values }
}

/// 10. HMA — Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n))
fn compute_hma(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    if period < 2 || period > n {
        return IndicatorResult { values: vec![0.0; n] };
    }
    let half = period / 2;
    let sqrt_p = (period as f64).sqrt() as usize;
    let wma_half = wma(&data.close, half.max(1));
    let wma_full = wma(&data.close, period);

    let mut diff = vec![0.0; n];
    for i in 0..n {
        if wma_half[i] != 0.0 && wma_full[i] != 0.0 {
            diff[i] = 2.0 * wma_half[i] - wma_full[i];
        }
    }
    IndicatorResult { values: wma(&diff, sqrt_p.max(1)) }
}

/// 11. ALMA — Arnaud Legoux Moving Average (Gaussian weighted)
fn compute_alma(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if period == 0 || period > n {
        return IndicatorResult { values };
    }
    let offset = 0.85;
    let sigma = 6.0;
    let m = offset * (period as f64 - 1.0);
    let s = period as f64 / sigma;

    // Pre-compute weights
    let mut weights = vec![0.0; period];
    let mut w_sum = 0.0;
    for i in 0..period {
        let w = (-((i as f64 - m) * (i as f64 - m)) / (2.0 * s * s)).exp();
        weights[i] = w;
        w_sum += w;
    }
    for w in weights.iter_mut() {
        *w /= w_sum;
    }

    for i in (period - 1)..n {
        let mut sum = 0.0;
        for j in 0..period {
            sum += data.close[i - period + 1 + j] * weights[j];
        }
        values[i] = sum;
    }
    IndicatorResult { values }
}

/// 12. ZLEMA — Zero-Lag EMA: EMA of (close + (close - close[lag]))
fn compute_zlema(data: &OhlcvData, period: usize) -> IndicatorResult {
    let n = data.len;
    let lag = (period.saturating_sub(1)) / 2;
    let mut adjusted = vec![0.0; n];
    for i in 0..n {
        if i >= lag {
            adjusted[i] = data.close[i] + (data.close[i] - data.close[i - lag]);
        } else {
            adjusted[i] = data.close[i];
        }
    }
    IndicatorResult { values: ema(&adjusted, period) }
}

/// 13. SWMA — Symmetrically Weighted Moving Average: [1,2,2,1]/6 for period 4
fn compute_swma(data: &OhlcvData, _period: usize) -> IndicatorResult {
    let n = data.len;
    let mut values = vec![0.0; n];
    if n < 4 {
        return IndicatorResult { values };
    }
    for i in 3..n {
        values[i] = (data.close[i - 3] + 2.0 * data.close[i - 2] + 2.0 * data.close[i - 1] + data.close[i]) / 6.0;
    }
    IndicatorResult { values }
}

/// 14. TRIMA — Triangular Moving Average: SMA of SMA
fn compute_trima(data: &OhlcvData, period: usize) -> IndicatorResult {
    let sma1 = sma(&data.close, period);
    IndicatorResult { values: sma(&sma1, period) }
}

/// Dispatch function for moving average indicators
pub fn dispatch(name: &str, period: usize, data: &OhlcvData) -> Option<IndicatorResult> {
    let result = match name.to_uppercase().as_str() {
        "SMA" => compute_sma(data, period),
        "EMA" => compute_ema(data, period),
        "WMA" => compute_wma(data, period),
        "DEMA" => compute_dema(data, period),
        "TEMA" => compute_tema(data, period),
        "KAMA" => compute_kama(data, period),
        "T3" => compute_t3(data, period),
        "VIDYA" => compute_vidya(data, period),
        "FRAMA" => compute_frama(data, period),
        "HMA" => compute_hma(data, period),
        "ALMA" => compute_alma(data, period),
        "ZLEMA" => compute_zlema(data, period),
        "SWMA" => compute_swma(data, period),
        "TRIMA" => compute_trima(data, period),
        _ => return None,
    };
    Some(result)
}
